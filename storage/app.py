from flask import Flask, jsonify, request, Response
import os
import glob

app = Flask(__name__)

LOG_DIR = "/app/logs"
LOG_FILE = f"{LOG_DIR}/record.log"

@app.route('/log', methods=['POST'])
def post_log():
    data = request.data.decode('utf-8')
    with open(LOG_FILE, "a") as f:
        f.write(data + "\n")
    return Response("OK\n", mimetype="text/plain"), 200

@app.route('/log', methods=['GET'])
def get_log():
    try:
        with open(LOG_FILE, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return Response(content, mimetype="text/plain"), 200

@app.route("/reset", methods=["POST"])
def reset_logs():
    """Delete all log files."""
    for log_file in glob.glob(f"{LOG_DIR}/*.log"):
        os.remove(log_file)
    return jsonify({"status": "Logs cleared"}), 200

if __name__ == "__main__":
    os.makedirs(LOG_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
