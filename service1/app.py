import os
import datetime
import requests
from flask import Flask, Response

app = Flask(__name__)
VSTORAGE_FILE = "/app/vstorage/log.txt"   # host-mounted dir -> file inside it

def uptime_hours():
    try:
        with open('/proc/uptime', 'r') as f:
            secs = float(f.readline().split()[0])
            return secs / 3600.0
    except Exception:
        return 0.0

def free_disk_mb():
    try:
        out = os.popen("df / --output=avail -m | tail -1").read().strip()
        return int(out.split()[0])
    except Exception:
        return 0

def timestamp_iso_utc():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

@app.route('/status', methods=['GET'])
def status():
    ts = timestamp_iso_utc()
    hours = uptime_hours()
    free_mb = free_disk_mb()
    record1 = f"{ts}: uptime {hours:.2f} hours, free disk in root: {free_mb} MBytes"

    # send to Storage container (container network)
    try:
        requests.post("http://storage:5000/log", data=record1, headers={"Content-Type": "text/plain"}, timeout=5)
    except Exception as e:
        app.logger.error("POST to storage failed: %s", e)

    # append to host-mounted vstorage
    try:
        os.makedirs(os.path.dirname(VSTORAGE_FILE), exist_ok=True)
        with open(VSTORAGE_FILE, "a") as f:
            f.write(record1 + "\n")
    except Exception as e:
        app.logger.error("Write to vstorage failed: %s", e)

    # forward to Service2 (container name)
    try:
        r = requests.get("http://service2:5000/status", timeout=5)
        record2 = r.text
    except Exception as e:
        record2 = f"Error contacting Service2: {e}"

    combined = record1 + "\n" + record2
    return Response(combined, mimetype="text/plain")


@app.route('/log', methods=['GET'])
def get_log():
    # Forward GET to Storage container
    try:
        r = requests.get("http://storage:5000/log", timeout=5)
        return Response(r.text, mimetype="text/plain"), r.status_code
    except Exception as e:
        return Response(f"Error contacting storage: {e}", mimetype="text/plain"), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

