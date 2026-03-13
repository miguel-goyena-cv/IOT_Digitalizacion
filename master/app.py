import serial
import time
from flask import Flask, render_template, request, jsonify

from awsiot import mqtt5_client_builder
from awscrt import mqtt5
import threading, time

import json
import time

app = Flask(__name__)

# --- Serial Communication Setup ---
# NOTE: Please replace '/dev/ttyACM0' with the correct serial port for your Arduino.
# On Raspberry Pi, it is typically /dev/ttyACM0 or /dev/ttyUSB0.
# You can find the correct port by checking the output of `dmesg | grep tty` after plugging in your Arduino.
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 9600

ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    time.sleep(2)  # Wait for the serial connection to initialize
except serial.SerialException as e:
    print(f"Error: Could not open serial port '{SERIAL_PORT}'. {e}")
    print("Please ensure the Arduino is connected and the correct serial port is specified in app.py.")


# Events and properties for AWS used within callbacks to progress sample
connection_success_event = threading.Event()
stopped_event = threading.Event()
received_all_event = threading.Event()
endpoint_AWS="a2xyhr7rc9cefs-ats.iot.us-east-1.amazonaws.com"
cert_filepath_AWS="cert/Casa1.cert.pem"
pri_key_filepath_AWS="cert/Casa1.private.key"
clientId_AWS="basicPubSub"
device_name_AWS="Casa1"
message_topic_commands_AWS="command"
message_topic_telemetry_AWS="telemetry"
client = None
iot_connected = False
TIMEOUT_CONNECT_AWS = 100

# Connection to AWS
def connect_to_aws():

    global client, iot_connected

    # Create MQTT5 client using mutual TLS via X509 Certificate and Private Key
    print("==== Creating MQTT5 Client ====\n")
    client = mqtt5_client_builder.mtls_from_path(
        endpoint=endpoint_AWS,
        cert_filepath=cert_filepath_AWS,
        pri_key_filepath=pri_key_filepath_AWS,
        on_publish_received=on_publish_received_AWS,
        on_lifecycle_stopped=on_lifecycle_stopped_AWS,
        on_lifecycle_attempting_connect=on_lifecycle_attempting_connect_AWS,
        on_lifecycle_connection_success=on_lifecycle_connection_success_AWS,
        on_lifecycle_connection_failure=on_lifecycle_connection_failure_AWS,
        on_lifecycle_disconnection=on_lifecycle_disconnection_AWS,
        client_id=clientId_AWS)
    
    # Start the client, instructing the client to desire a connected state. The client will try to 
    # establish a connection with the provided settings. If the client is disconnected while in this 
    # state it will attempt to reconnect automatically.
    print("==== Starting client ====")
    client.start()

    # We await the `on_lifecycle_connection_success` callback to be invoked.
    if not connection_success_event.wait(TIMEOUT_CONNECT_AWS):
        raise TimeoutError("Connection timeout")


    # Subscribe 
    print("==== Subscribing to topic '{}' ====".format(message_topic_commands_AWS))
    subscribe_future = client.subscribe(subscribe_packet=mqtt5.SubscribePacket(
        subscriptions=[mqtt5.Subscription(
            topic_filter=message_topic_commands_AWS,
            qos=mqtt5.QoS.AT_LEAST_ONCE)]
    ))
    suback = subscribe_future.result(TIMEOUT_CONNECT_AWS)
    print("Suback received with reason code:{}\n".format(suback.reason_codes))

    iot_connected = True

# Callback when any IOT PUB is received
def on_publish_received_AWS(publish_packet_data):
    publish_packet = publish_packet_data.publish_packet
    print("==== Received message from topic '{}': {} ====\n".format(
        publish_packet.topic, publish_packet.payload.decode('utf-8')))

    # What to do with message
    # Format the command for LCD messages
    command = json.loads(publish_packet.payload.decode('utf-8'))
    if command['house'] == "Casa1":
        print("Message for Casa1\n")
        if command['device'] == "LCD":
            print("Message for LCD\n")
            message = command['message']
            commandToHouse = f'lcd "{message}"'
            response = send_command(commandToHouse)
            print(f"Response from HOUSE {response}")


# Callback for the lifecycle event Stopped
def on_lifecycle_stopped_AWS(lifecycle_stopped_data: mqtt5.LifecycleStoppedData):
    print("Lifecycle Stopped\n")
    stopped_event.set()


# Callback for lifecycle event Attempting Connect
def on_lifecycle_attempting_connect_AWS(lifecycle_attempting_connect_data: mqtt5.LifecycleAttemptingConnectData):
    print("Lifecycle Connection Attempt\nConnecting to endpoint: '{}' with client ID'{}'".format(
        endpoint_AWS, clientId_AWS))


# Callback for the lifecycle event Connection Success
def on_lifecycle_connection_success_AWS(lifecycle_connect_success_data: mqtt5.LifecycleConnectSuccessData):
    connack_packet = lifecycle_connect_success_data.connack_packet
    print("Lifecycle Connection Success with reason code:{}\n".format(
        repr(connack_packet.reason_code)))
    connection_success_event.set()


# Callback for the lifecycle event Connection Failure
def on_lifecycle_connection_failure_AWS(lifecycle_connection_failure: mqtt5.LifecycleConnectFailureData):
    print("Lifecycle Connection Failure with exception:{}".format(
        lifecycle_connection_failure.exception))


# Callback for the lifecycle event Disconnection
def on_lifecycle_disconnection_AWS(lifecycle_disconnect_data: mqtt5.LifecycleDisconnectData):
    print("Lifecycle Disconnected with reason code:{}".format(
        lifecycle_disconnect_data.disconnect_packet.reason_code if lifecycle_disconnect_data.disconnect_packet else "None"))


def send_command(command):
    """Sends a command to the Arduino and reads the response."""
    if not ser or not ser.is_open:
        return ["Serial port is not available."]
    
    print(f"Sending command: {command}")
    ser.write((command + '\n').encode('utf-8'))
    
    # Wait a moment for the Arduino to process and respond
    time.sleep(0.5) 
    
    responses = []
    while ser.in_waiting > 0:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                responses.append(line)
        except UnicodeDecodeError:
            pass # Ignore occasional decoding errors
            
    print(f"Received response: {responses}")
    return responses if responses else ["No response from device."]

# --- Web Routes ---

@app.route('/')
def index():
    """Renders the main control panel page."""
    return render_template(
        'index.html',
        endpoint_AWS=endpoint_AWS,
        cert_filepath_AWS=cert_filepath_AWS,
        pri_key_filepath_AWS=pri_key_filepath_AWS,
        clientId_AWS=clientId_AWS,
        device_name_AWS=device_name_AWS,
        message_topic_commands_AWS=message_topic_commands_AWS,
        message_topic_telemetry_AWS=message_topic_telemetry_AWS
    )

@app.route("/aws")
def aws_config():

    return render_template(
        "aws_config.html",
        title="AWS Configuration",
        endpoint_AWS=endpoint_AWS,
        cert_filepath_AWS=cert_filepath_AWS,
        pri_key_filepath_AWS=pri_key_filepath_AWS,
        clientId_AWS=clientId_AWS,
        device_name_AWS=device_name_AWS,
        message_topic_commands_AWS=message_topic_commands_AWS,
        message_topic_telemetry_AWS=message_topic_telemetry_AWS
    )

@app.route('/control', methods=['POST'])
def control():
    """Handles generic commands like LED, buzzer, and servo control."""
    command = request.form.get('command')
    if not command:
        return jsonify({"status": "error", "message": "No command provided."}), 400
        
    # Format the command for LCD messages
    if command.startswith("lcd"):
        message = request.form.get('message', '')
        command = f'lcd "{message}"'

    response = send_command(command)
    return jsonify({"status": "success", "command": command, "response": response})

@app.route('/sensors')
def get_sensors():
    """Specifically handles the 'sensors' command to fetch all sensor data."""
    if not ser or not ser.is_open:
        return jsonify({"error": "Serial port not available."})

    ser.flushInput()  # Clear any old data in the input buffer
    response_lines = send_command("sensors")
    
    sensor_data = {}
    for line in response_lines:
        if "Result: " in line:
            # Parse lines like "Result: Temperature: 24.00C"
            try:
                key_part, value_part = line.split("Result: ", 1)[1].split(': ', 1)
                key = key_part.strip().lower().replace(" ", "_")
                sensor_data[key] = value_part.strip()
            except ValueError:
                # Handle lines without a key-value structure, like "Result: Fire Detected!"
                key = "status"
                value = line.split("Result: ", 1)[1]
                if "fire" in value.lower():
                    sensor_data["fire_safety"] = value
                elif "noise" in value.lower():
                    sensor_data["noise_status"] = value
                elif "intruder" in value.lower():
                    sensor_data["motion_status"] = value

    # Add data for the IOT Message routing
    sensor_data["house"] = device_name_AWS
    sensor_data["timestamp"] = int(time.time())

    print(f"Parsed Sensor Data: {sensor_data}")
    mesage_json = json.dumps(sensor_data)

    # We send json message to IOTCore AWS
    if iot_connected:
        print(f"Publishing message to topic '{message_topic_telemetry_AWS}': {mesage_json}")
        publish_future = client.publish(
            mqtt5.PublishPacket(
                topic=message_topic_telemetry_AWS,
                payload=mesage_json,
                qos=mqtt5.QoS.AT_LEAST_ONCE
            )
        )

        publish_completion_data = publish_future.result(TIMEOUT_CONNECT_AWS)
        print("PubAck received with {}\n".format(repr(publish_completion_data.puback.reason_code)))

    return jsonify(sensor_data)

@app.route('/connect_iot', methods=['POST'])
def connect_iot():

    global endpoint_AWS
    global cert_filepath_AWS
    global pri_key_filepath_AWS
    global clientId_AWS
    global device_name_AWS
    global message_topic_commands_AWS
    global message_topic_telemetry_AWS

    endpoint_AWS = request.form.get("endpoint_AWS")
    cert_filepath_AWS = request.form.get("cert_filepath_AWS")
    pri_key_filepath_AWS = request.form.get("pri_key_filepath_AWS")
    clientId_AWS = request.form.get("clientId_AWS")
    device_name_AWS = request.form.get("device_name_AWS")
    message_topic_commands_AWS = request.form.get("message_topic_commands_AWS")
    message_topic_telemetry_AWS = request.form.get("message_topic_telemetry_AWS")

    try:

        connect_to_aws()

        return jsonify({
            "status": "success",
            "message": "Connected to AWS IoT"
        })

    except Exception as e:

        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == '__main__':

    print("Starting Flask server. Open http://<your-pi-ip-address>:5000 in a browser.")
    app.run(host='0.0.0.0', port=5000)




