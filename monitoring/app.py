from flask import Flask
import requests

app = Flask(__name__)

@app.route("/health")
def health():
    try:
        r = requests.get("http://storage:5000/log")
        return {"storage_status": "ok" if r.status_code == 200 else "down"}
    except:
        return {"storage_status": "down"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7000)

