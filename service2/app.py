from flask import Flask, Response
import subprocess
import requests
import datetime

app = Flask(__name__)


def uptime_hours():
    try:
        with open("/proc/uptime", "r") as f:
            secs = float(f.readline().split()[0])
            return secs / 3600.0
    except Exception:
        return 0.0


def free_disk_mb():
    try:
        out = subprocess.check_output(
            ["sh", "-c", "df / --output=avail -m | tail -1"],
            text=True
        ).strip()
        return out.split()[0]
    except Exception:
        return "0"


def timestamp_iso_utc():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@app.route("/status", methods=["GET"])
def status():
    ts = timestamp_iso_utc()
    hours = uptime_hours()
    free_mb = free_disk_mb()

    record = f"{ts}: uptime {hours:.2f} hours, free disk in root: {free_mb} MBytes"

    # POST to storage
    try:
        requests.post(
            "http://storage:5000/log",
            data=record,
            headers={"Content-Type": "text/plain"},
            timeout=5
        )
    except Exception as e:
        app.logger.error(f"POST to storage failed: {e}")

    return Response(record, mimetype="text/plain")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
