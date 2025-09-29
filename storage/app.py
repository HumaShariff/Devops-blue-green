# storage/app.py
from flask import Flask, request, Response
import os

app = Flask(__name__)
LOGFILE = "/data/log.txt"   # stored inside Docker named volume

@app.route('/log', methods=['POST'])
def post_log():
    data = request.data.decode('utf-8')
    os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)
    with open(LOGFILE, "a") as f:
        f.write(data + "\n")
    return Response("OK\n", mimetype="text/plain"), 200

@app.route('/log', methods=['GET'])
def get_log():
    try:
        with open(LOGFILE, "r") as f:
            content = f.read()
    except FileNotFoundError:
        content = ""
    return Response(content, mimetype="text/plain"), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

