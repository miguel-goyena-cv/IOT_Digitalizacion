import json
from flask import Flask, render_template
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def index():

    with open("../datos.json") as f:
        data = json.load(f)

    items = data["Items"]

    timestamps = []
    temperature = []
    humidity = []
    distance = []

    for item in items:

        payload = item["payload"]["M"]

        ts = int(payload["timestamp"]["N"])
        timestamps.append(datetime.fromtimestamp(ts).strftime("%H:%M:%S"))

        temp = float(payload["temperature"]["S"].replace("C",""))
        temperature.append(temp)

        hum = float(payload["humidity"]["S"].replace("%",""))
        humidity.append(hum)

        dist = float(payload["distance"]["S"].replace(" cm",""))
        distance.append(dist)

    return render_template(
        "index.html",
        timestamps=timestamps,
        temperature=temperature,
        humidity=humidity,
        distance=distance
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)