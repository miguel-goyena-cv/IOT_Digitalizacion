import json
import subprocess
import threading
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta

from awsiot import mqtt5_client_builder
from awscrt import mqtt5

app = Flask(__name__)



@app.route("/")
def index():

    with open("../datos.json") as f:
        data = json.load(f)

    items = data["Items"]

    # Obtener lista de casas únicas
    houses = list(set(item["house"]["S"] for item in items))

    # Casa seleccionada (por defecto la primera)
    selected_house = request.args.get("house", houses[0])

    timestamps = []
    temperature = []
    humidity = []
    distance = []

    today = datetime.now().date()

    for item in items:

        if item["house"]["S"] != selected_house:
            continue

        payload = item["payload"]["M"]

        ts = int(payload["timestamp"]["N"])
        dt = datetime.fromtimestamp(ts)

        # Filtrar solo datos de hoy
        if dt.date() != today:
            continue

        timestamps.append(datetime.fromtimestamp(ts).strftime("%d/%m %H:%M:%S"))

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
        distance=distance,
        houses=houses,
        selected_house=selected_house
    )

@app.route("/send", methods=["POST"])
def send():

    import json

    message = request.form.get("message")
    house = request.form.get("house")

    try:
        # Convertir string → dict
        data = json.loads(message)

        # Inyectar house
        data["house"] = house

        # Volver a string JSON listo para enviar
        final_message = json.dumps(data)

        print("JSON enviado a IoT:", final_message)

    except Exception as e:
        print("Error procesando JSON:", e)

    if house:
        return redirect(url_for("index", house=house))
    else:
        return redirect(url_for("index"))

@app.route("/refresh")
def refresh():

    print("Entro en refresh")
    house = request.form.get("house")
    
    now = datetime.now()

    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1)

    start_ts = int(start_of_day.timestamp())
    end_ts = int(end_of_day.timestamp())

    command = f"""aws dynamodb scan \
    --table-name telemetry \
    --filter-expression "#ts BETWEEN :start AND :end" \
    --expression-attribute-names '{{"#ts":"timestamp"}}' \
    --expression-attribute-values '{{":start":{{"N":"{start_ts}"}},":end":{{"N":"{end_ts}"}}}}' \
    --output json > ../datos.json"""

    print("Comando ejecutado:")
    print(command)

    subprocess.run(command, shell=True)

    return redirect(url_for("index", house=house))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)