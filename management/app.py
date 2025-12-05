from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import requests
import os
import docker
import datetime
import humanize
import jwt

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mysecretkey")

STORAGE_URL = "http://storage:5000"
MGMT_USER = os.environ.get("MGMT_USER", "admin")
ACTIVE_VERSION_FILE = "/tmp/active_version.txt"

JWT_SECRET = os.environ.get("JWT_SECRET", "supersecret")
JWT_ALGO = "HS256"

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
# Management console
# -------------------------
@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    # Fetch logs
    try:
        logs = requests.get(f"{STORAGE_URL}/log").text
    except Exception as e:
        logs = f"Error fetching logs: {e}"

    # Active version
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active = f.read().strip()
    except FileNotFoundError:
        active = "blue"

    # Monitoring info
    containers = ["devops-service1_blue-1", "devops-service1_green-1", "devops-storage-1"]
    stats = {}
    for c in containers:
        stats[c] = get_container_stats(c)

    # Log sizes
    log_sizes = get_log_sizes()

    return render_template("index.html", logs=logs, active_version=active, stats=stats, log_sizes=log_sizes)

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

    # Update nginx upstream inside gateway container
    nginx_conf = f"""
    upstream service1_backend {{
        server devops-service1_{new_version}-1:5000;
    }}

    server {{
        listen 8199;
        location / {{
            proxy_pass http://service1_backend;
        }}
    }}
    """
    tmp_conf = "/tmp/upstream.conf"
    with open(tmp_conf, "w") as f:
        f.write(nginx_conf)
    os.system(f"docker cp {tmp_conf} devops-gateway-1:/etc/nginx/conf.d/upstream.conf")
    os.system("docker exec devops-gateway-1 nginx -s reload")

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
        container = client.containers.get(container_name)
        container.stop()
        return redirect(url_for("index"))
    except docker.errors.NotFound:
        return redirect(url_for("index"))

@app.route("/reset_log", methods=["POST"])
def reset_log():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        requests.post(f"{STORAGE_URL}/reset")
        return redirect(url_for("index"))
    except Exception as e:
        return f"Error resetting log: {e}"

# -------------------------
# JWT Token
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
# API /status with JWT
# -------------------------
@app.route("/status", methods=["GET"])
def status_proxy():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "Unauthorized: Missing token", 401

    token = auth.split()[1]
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return "Token expired", 401
    except jwt.InvalidTokenError:
        return "Invalid token", 401

    # Forward request to active service
    active_version = "blue"
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active_version = f.read().strip()
    except FileNotFoundError:
        pass

    url = f"http://service1_{active_version}-1:5000/status"
    resp = requests.get(url)
    return (resp.content, resp.status_code, resp.headers.items())

# -------------------------
# Helpers
# -------------------------
def get_container_stats(container_name):
    try:
        container = client.containers.get(container_name)
        started_at = container.attrs["State"]["StartedAt"]
        started_at_dt = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        uptime = datetime.datetime.now(datetime.timezone.utc) - started_at_dt
        stats = container.stats(stream=False)
        cpu_percent = calculate_cpu_percent(stats)
        mem_usage = stats["memory_stats"]["usage"] / (1024 * 1024)
        mem_limit = stats["memory_stats"].get("limit", 0) / (1024 * 1024)
        return {
            "uptime": humanize.naturaldelta(uptime),
            "cpu_percent": round(cpu_percent, 2),
            "mem_usage": round(mem_usage, 2),
            "mem_limit": round(mem_limit, 2)
        }
    except docker.errors.NotFound:
        return {"error": "Container not found"}
    except Exception as e:
        return {"error": str(e)}

def calculate_cpu_percent(stats):
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = 0.0
        percpu = stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [1])
        if system_delta > 0.0 and cpu_delta > 0.0:
            cpu_percent = (cpu_delta / system_delta) * len(percpu) * 100.0
        return cpu_percent
    except KeyError:
        return 0.0

def get_log_sizes():
    try:
        r = requests.get(f"{STORAGE_URL}/log")
        logs_text = r.text
        if not logs_text.strip():
            return {}
        total_size = len(logs_text.encode("utf-8"))
        return {"storage_logs.txt": total_size}
    except Exception:
        return {}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
