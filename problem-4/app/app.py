from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def home():
    return "<h1>Hello from Amazon ECS</h1>"


@app.get("/health/live")
def live():
    return jsonify(status="ok")


@app.get("/health/ready")
def ready():
    return jsonify(status="ready")
