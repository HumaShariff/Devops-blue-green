from flask import Flask, jsonify
import os
import glob

app = Flask(__name__)

LOG_DIR = "/app/logs"

@app.route("/log", methods=["GET"])
def get_logs():
    """Return the aggregated log content."""
    logs = ""
    for log_file in glob.glob(f"{LOG_DIR}/*.log"):
        with open(log_file, "r") as f:
            logs += f.read() + "\n"
    return logs, 200

@app.route("/reset", methods=["POST"])
def reset_logs():
    """Delete all log files."""
    for log_file in glob.glob(f"{LOG_DIR}/*.log"):
        os.remove(log_file)
    return jsonify({"status": "Logs cleared"}), 200

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
