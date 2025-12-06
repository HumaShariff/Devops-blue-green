from flask import Flask, render_template, request, redirect, url_for, session, Response
import requests
import os
import docker
import datetime
import humanize
import jwt
import psutil   # host cpu
import glob

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mysecretkey")

STORAGE_URL = "http://storage:5000"
MGMT_USER = os.environ.get("MGMT_USER", "admin")
ACTIVE_VERSION_FILE = "/tmp/active_version.txt"

JWT_SECRET = os.environ.get("JWT_SECRET", "supersecret")
JWT_ALGO = "HS256"

# Docker client (requires /var/run/docker.sock mounted into container)
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

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

    # logs (text) from storage
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

    # containers to monitor (adjust names if your compose names differ)
    containers = [
        "devops-service1_blue-1",
        "devops-service1_green-1",
        "devops-storage-1"
    ]

    stats = {}
    for name in containers:
        stats[name] = get_container_stats(name)

    # minimal log size: total bytes of storage /log response (works even if storage aggregates)
    log_sizes = get_log_sizes_by_forwarding()

    # host cpu util
    host_cpu = get_host_cpu_percent()

    return render_template(
        "index.html",
        logs=logs_text,
        active_version=active,
        stats=stats,
        log_sizes=log_sizes,
        host_cpu=host_cpu
    )

# -------------------------
# Actions: switch, discard, reset
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
# JWT token
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
# Proxy endpoints (require JWT)
# -------------------------
@app.route("/status", methods=["GET", "POST"])
def status_proxy():
    return forward_to_active("status", method=request.method)

@app.route("/log", methods=["GET", "POST"])
def log_proxy():
    return forward_to_active("log", method=request.method)

def forward_to_active(endpoint, method="GET"):
    # Basic JWT check
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
        if method.upper() == "GET":
            r = requests.get(target, timeout=5)
        else:
            r = requests.post(target, data=request.data, timeout=5)
        return Response(r.content, status=r.status_code, mimetype=r.headers.get("Content-Type", "text/plain"))
    except Exception as e:
        return f"Error contacting active service: {e}", 502

# -------------------------
# Monitoring helpers
# -------------------------
def get_container_stats(container_name):
    """Return dict: uptime (natural), cpu_percent (container), memory usage MB, memory limit MB"""
    try:
        container = client.containers.get(container_name)
    except docker.errors.NotFound:
        return {"error": "container not found"}

    try:
        # Uptime
        started = container.attrs["State"].get("StartedAt", None)
        if started:
            started_dt = datetime.datetime.fromisoformat(started.replace("Z", "+00:00"))
            uptime_td = datetime.datetime.now(datetime.timezone.utc) - started_dt
            uptime = humanize.naturaldelta(uptime_td)
        else:
            uptime = "N/A"

        # stats (may miss some fields depending on engine)
        stats = container.stats(stream=False)

        # memory
        mem_usage = stats.get("memory_stats", {}).get("usage", 0) / (1024 * 1024)
        mem_limit = stats.get("memory_stats", {}).get("limit", 0) / (1024 * 1024)

        # cpu percent
        cpu_percent = calculate_cpu_percent(stats)

        return {
            "uptime": uptime,
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage": round(mem_usage, 2),
            "mem_limit": round(mem_limit, 2)
        }
    except Exception as e:
        return {"error": str(e)}

def calculate_cpu_percent(stats):
    try:
        cpu_total = stats["cpu_stats"]["cpu_usage"]["total_usage"]
        precpu_total = stats["precpu_stats"]["cpu_usage"].get("total_usage", 0)
        cpu_delta = cpu_total - precpu_total

        system_total = stats["cpu_stats"].get("system_cpu_usage", 0)
        precpu_system = stats["precpu_stats"].get("system_cpu_usage", 0)
        system_delta = system_total - precpu_system

        percpu = stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])
        cpus = len(percpu) if isinstance(percpu, list) and len(percpu) > 0 else 1

        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * cpus * 100.0
        return 0.0
    except Exception:
        return 0.0

def get_log_sizes_by_forwarding():
    """Minimal: ask storage /log and compute bytes of returned text (works for assignment)."""
    try:
        r = requests.get(f"{STORAGE_URL}/log", timeout=3)
        text = r.text or ""
        return {"storage_logs.txt": len(text.encode("utf-8"))}
    except Exception:
        return {}

def get_host_cpu_percent():
    """Use psutil if available; return a float (0-100). Uses a very short blocking interval."""
    try:
        # short interval (blocks ~0.1s) — acceptable for on-demand dashboard
        val = psutil.cpu_percent(interval=0.1)
        return round(val, 1)
    except Exception:
        # fallback: return 0 if psutil not available / fails
        return 0.0

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
