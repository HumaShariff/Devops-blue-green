from flask import Flask, render_template, request, redirect, url_for, session, Response
import requests
import os
import docker
import datetime
import humanize
import jwt
import psutil
import time

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mysecretkey")

STORAGE_URL = "http://storage:5000"
MGMT_USER = os.environ.get("MGMT_USER", "admin")
ACTIVE_VERSION_FILE = "/tmp/active_version.txt"

JWT_SECRET = os.environ.get("JWT_SECRET", "supersecret")
JWT_ALGO = "HS256"

# Docker client
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

# -------------------------
# Global monitoring state
# -------------------------
RESPONSE_TIMES = {}  # {"endpoint_name": [times_in_ms]}
MAX_HISTORY = 50

LAST_ALIVE = {}  # {"container_name": datetime.datetime}

# -------------------------
# Login / Logout
# -------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == MGMT_USER and password == "password":
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

# -------------------------
# Dashboard
# -------------------------
@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # logs from storage
    try:
        logs_text = requests.get(f"{STORAGE_URL}/log", timeout=3).text
    except Exception as e:
        logs_text = f"Error fetching logs: {e}"

    # active version
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active = f.read().strip()
    except FileNotFoundError:
        active = "blue"

    containers = [
        "devops-service1_blue-1",
        "devops-service1_green-1",
        "devops-storage-1"
    ]

    stats = {}
    last_alive_times = {}
    for name in containers:
        stats[name] = get_container_cpu_memory(name)
        last_alive_times[name] = get_last_alive_status(name)

    log_sizes = get_log_sizes_by_forwarding()
    host_cpu = get_host_cpu_percent()

    status_stats = get_response_time_stats("status")
    log_stats = get_response_time_stats("log")

    return render_template(
        "index.html",
        logs=logs_text,
        active_version=active,
        stats=stats,
        log_sizes=log_sizes,
        host_cpu=host_cpu,
        status_stats=status_stats,
        log_stats=log_stats,
        last_alive_times=last_alive_times
    )

# -------------------------
# Actions
# -------------------------
@app.route("/switch_version", methods=["POST"])
def switch_version():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            current = f.read().strip()
    except FileNotFoundError:
        current = "blue"
    new_version = "green" if current == "blue" else "blue"
    with open(ACTIVE_VERSION_FILE, "w") as f:
        f.write(new_version)
    return redirect(url_for("index"))

@app.route("/discard_old", methods=["POST"])
def discard_old():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active = f.read().strip()
    except FileNotFoundError:
        active = "blue"
    old = "green" if active == "blue" else "blue"
    container_name = f"devops-service1_{old}-1"
    try:
        c = client.containers.get(container_name)
        c.stop()
    except docker.errors.NotFound:
        pass
    return redirect(url_for("index"))

@app.route("/reset_log", methods=["POST"])
def reset_log():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        requests.post(f"{STORAGE_URL}/reset", timeout=3)
    except Exception as e:
        return f"Error resetting log: {e}"
    return redirect(url_for("index"))

# -------------------------
# JWT
# -------------------------
@app.route("/get_token")
def get_token():
    if not session.get("logged_in"):
        return "Not logged in", 401
    payload = {
        "user": MGMT_USER,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)
    return f"JWT token: {token}"

# -------------------------
# Proxy endpoints
# -------------------------
@app.route("/status", methods=["GET", "POST"])
def status_proxy():
    return forward_to_active("status", method=request.method)

@app.route("/log", methods=["GET", "POST"])
def log_proxy():
    return forward_to_active("log", method=request.method)

def forward_to_active(endpoint, method="GET"):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "Unauthorized: Missing token", 401
    token = auth.split()[1]
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return "Invalid token", 401

    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active = f.read().strip()
    except FileNotFoundError:
        active = "blue"

    target = f"http://devops-service1_{active}-1:5000/{endpoint.lstrip('/')}"
    try:
        start_time = time.time()
        if method.upper() == "GET":
            r = requests.get(target, timeout=5)
        else:
            r = requests.post(target, data=request.data, timeout=5)
        elapsed_ms = (time.time() - start_time) * 1000

        # record response time
        if endpoint not in RESPONSE_TIMES:
            RESPONSE_TIMES[endpoint] = []
        RESPONSE_TIMES[endpoint].append(elapsed_ms)
        RESPONSE_TIMES[endpoint] = RESPONSE_TIMES[endpoint][-MAX_HISTORY:]

        # record last alive for container
        container_name = f"devops-service1_{active}-1"
        LAST_ALIVE[container_name] = datetime.datetime.utcnow()

        return Response(r.content, status=r.status_code, mimetype=r.headers.get("Content-Type", "text/plain"))
    except Exception as e:
        return f"Error contacting active service: {e}", 502

def get_response_time_stats(endpoint):
    times = RESPONSE_TIMES.get(endpoint, [])
    if not times:
        return {"min": None, "max": None, "avg": None}
    return {
        "min": round(min(times), 2),
        "max": round(max(times), 2),
        "avg": round(sum(times)/len(times), 2)
    }

# -------------------------
# Monitoring helpers
# -------------------------
def get_container_cpu_memory(container_name):
    """
    Returns CPU %, memory usage/limit, and uptime.
    Shows 'Stopped' if container is not running.
    """
    try:
        container = client.containers.get(container_name)

        # Uptime calculation with Stopped check
        if container.status != "running":
            uptime = "Stopped"
        else:
            started = container.attrs["State"].get("StartedAt", None)
            if started:
                started_dt = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
                uptime = humanize.naturaldelta(datetime.datetime.now(datetime.timezone.utc) - started_dt)
            else:
                uptime = "N/A"

        # CPU & Memory stats
        stats = container.stats(stream=False)
        cpu_percent = calculate_cpu_percent(stats)
        mem_usage = stats.get("memory_stats", {}).get("usage", 0) / (1024*1024)
        mem_limit = stats.get("memory_stats", {}).get("limit", 0) / (1024*1024)

        return {
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage": round(mem_usage, 2),
            "mem_limit": round(mem_limit, 2),
            "uptime": uptime
        }

    except docker.errors.NotFound:
        return {"error": "Container not found"}
    except Exception as e:
        return {"error": str(e)}

def calculate_cpu_percent(stats):
    try:
        cpu_total = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        precpu_total = stats["precpu_stats"]["cpu_usage"].get("total_usage",0)
        cpu_delta = cpu_total - precpu_total
        system_total = stats["cpu_stats"].get("system_cpu_usage",0)
        precpu_system = stats["precpu_stats"].get("system_cpu_usage",0)
        percpu = stats["cpu_stats"]["cpu_usage"].get("percpu_usage",[])
        cpus = len(percpu) if isinstance(percpu,list) and len(percpu)>0 else 1
        if system_delta>0 and cpu_delta>0:
            return (cpu_delta/system_delta)*cpus*100.0
        return 0.0
    except:
        return 0.0

def get_last_alive_status(container_name):
    last = LAST_ALIVE.get(container_name)
    if not last:
        return "Never"
    delta = datetime.datetime.utcnow() - last
    if delta.total_seconds() < 10:
        return "Living"
    return humanize.naturaldelta(delta) + " ago"

def get_log_sizes_by_forwarding():
    try:
        r = requests.get(f"{STORAGE_URL}/log", timeout=3)
        text = r.text or ""
        return {"storage_logs.txt": len(text.encode("utf-8"))}
    except:
        return {}

def get_host_cpu_percent():
    try:
        return round(psutil.cpu_percent(interval=0.1),1)
    except:
        return 0.0

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
