from flask import Flask, jsonify
import os, glob

app = Flask(__name__)

LOG_DIR = "/app/logs"

@app.route("/log")
def get_logs():
    logs = ""
    for f in glob.glob(f"{LOG_DIR}/*.log"):
        with open(f, "r") as file:
            logs += file.read() + "\n"
    return logs

@app.route("/reset", methods=["POST"])
def reset_logs():
    for f in glob.glob(f"{LOG_DIR}/*.log"):
        os.remove(f)
    return jsonify({"status": "Logs cleared"}), 200

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)  # ensure logs folder exists
    app.run(host="0.0.0.0", port=5000)
