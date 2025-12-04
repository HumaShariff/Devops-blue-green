from flask import Flask, render_template, request, redirect, url_for, session
import requests
import os
import docker

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "mysecretkey")

STORAGE_URL = "http://storage:5000/log"
GATEWAY_URL = "http://gateway:80"
MGMT_USER = os.environ.get("MGMT_USER", "admin")
ACTIVE_VERSION_FILE = "/tmp/active_version.txt"

client = docker.DockerClient(base_url='unix://var/run/docker.sock')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == MGMT_USER and password == "password":  # simple check, could use env
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    # Fetch logs
    try:
        logs = requests.get(STORAGE_URL).text
    except Exception as e:
        logs = f"Error fetching logs: {e}"
    # Show active version
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            active = f.read().strip()
    except FileNotFoundError:
        active = "blue"
    return render_template("index.html", logs=logs, active_version=active)

@app.route("/switch_version", methods=["POST"])
def switch_version():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    # Read current active version
    try:
        with open(ACTIVE_VERSION_FILE, "r") as f:
            current = f.read().strip()
    except FileNotFoundError:
        current = "blue"
    # Switch version
    new_version = "green" if current == "blue" else "blue"
    with open(ACTIVE_VERSION_FILE, "w") as f:
        f.write(new_version)
    # Tell gateway
    try:
        requests.post(f"{GATEWAY_URL}/set_backend", json={"active": new_version})
    except:
        pass
    return f"SWITCH VERSION triggered! Now active: {new_version}"

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
        return f"DISCARD OLD triggered! Stopped: {old}"
    except docker.errors.NotFound:
        return f"Container {container_name} not found!"

@app.route("/reset_log", methods=["POST"])
def reset_log():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    try:
        requests.post("http://storage:5000/reset")
        return "RESET LOG triggered! Logs cleared."
    except Exception as e:
        return f"Error resetting log: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
