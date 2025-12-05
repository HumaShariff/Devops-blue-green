import os
import datetime
import requests
from flask import Flask, Response

app = Flask(__name__)
# VSTORAGE_FILE = "/app/vstorage/log.txt"   # host-mounted dir -> file inside it

def uptime_minutes():
    """Return system uptime in minutes."""
    try:
        with open('/proc/uptime', 'r') as f:
            secs = float(f.readline().split()[0])
            return secs / 60.0   # minutes
    except Exception:
        return 0.0

def free_disk_mb():
    """Return available disk space in MB."""
    try:
        out = os.popen("df / --output=avail -m | tail -1").read().strip()
        return int(out.split()[0])
    except Exception:
        return 0

def timestamp_iso_utc():
    """Return current UTC timestamp in ISO format."""
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

@app.route('/status', methods=['GET'])
def status():
    """Return system status and log it to storage."""
    timestamp = timestamp_iso_utc()
    uptime = uptime_minutes()
    free_space = free_disk_mb()
    record = f"{timestamp}: uptime {uptime:.2f} minutes, free disk in root: {free_space} MBytes"

    # Send to Storage container
    try:
        requests.post("http://storage:5000/log", data=record, headers={"Content-Type": "text/plain"}, timeout=5)
    except Exception as e:
        app.logger.error("POST to storage failed: %s", e)

    return Response(record, mimetype="text/plain")

@app.route('/log', methods=['GET'])
def get_log():
    """Return log from storage container."""
    try:
        r = requests.get("http://storage:5000/log", timeout=5)
        return Response(r.text, mimetype="text/plain"), r.status_code
    except Exception as e:
        return Response(f"Error contacting storage: {e}", mimetype="text/plain"), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
