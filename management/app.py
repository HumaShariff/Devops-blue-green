from flask import Flask, render_template
import requests

app = Flask(__name__)

STORAGE_URL = "http://storage:5000/log"

@app.route("/")
def index():
    logs = requests.get(STORAGE_URL).text
    return render_template("index.html", logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

