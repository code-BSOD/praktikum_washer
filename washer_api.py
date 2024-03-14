# Importing necessary imports (libraries and framework)
from bottle import run, get, put
import random
import sys
import time
import json
from paho.mqtt import client as mqtt_client

# --------------------------------------------------------------------
# Custom Timer Class to calculate the on and off elapsed time of socket start

class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class"""

class Timer:
    def __init__(self):
        self._start_time = None

    def start(self):
        """Start a new timer"""
        if self._start_time is not None:
            raise TimerError(f"Timer is running. Use .stop() to stop it")

        self._start_time = time.perf_counter()

    def stop(self):
        """Stop the timer, and report the elapsed time"""
        if self._start_time is None:
            raise TimerError(f"Timer is not running. Use .start() to start it")

        elapsed_time = time.perf_counter() - self._start_time
        self._start_time = None
        return elapsed_time

# Custom Timer Class end
# --------------------------------------------------------------------



# --------------------------------------------------------------------
# MQTT Client Configs start

# Random MQTT Client ID
client_id = f"python_mqtt-{random.randint(0, 100)}"
client_id_sub = f"python_mqtt-{random.randint(0, 1000)}"
server_ip_address = "192.168.0.105"

# Creating the MQTT Client
client = mqtt_client.Client(client_id=client_id) # client for publishing commands
sub_client = mqtt_client.Client(client_id=client_id_sub) # client for subscribing to topic

# MQTT Client Configs end
# --------------------------------------------------------------------


# --------------------------------------------------------------------
# SUBSCRIBER Code Start

# List to save power on/off status and for sensor, energy readings are saved at every 10s interval
power_toggle_status = [] # for power status on/off
sensor_energy_reading = [] # for energy reading from telemetry

# Adding subscriber callback function
def onMessage(client, userdata, msg):
    # print(msg.topic + ": " + msg.payload.decode() + " from here")
    data = json.loads(msg.payload.decode())
    
    # Using global list
    global power_toggle_status
    global sensor_energy_reading

    # For appending power and sensor data to appropriate lists
    if "POWER" in data:
        power_toggle_status.append(data)
        # remove if list entry crosses 50
        if len(power_toggle_status) > 50:
            power_toggle_status = power_toggle_status[-50:]
    else:
        sensor_energy_reading.append(data)
        # remove if list entry crosses 50
        if len(sensor_energy_reading) > 50:
            sensor_energy_reading = sensor_energy_reading[-50:]


# Subscriber Callback function when a message is received from MQTT broker
sub_client.on_message = onMessage

# Check subscriber connection to broker
if sub_client.connect(server_ip_address, 1883, 60) != 0:
    print("Could NOT connect to broker for Subscription")
    sys.exit(-1)

# Subscriber Topics
sub_client.subscribe('stat/washer/RESULT') # to receive power toggle on/off data
sub_client.subscribe('tele/washer/SENSOR') # to receive energy telemetry data from sensor every 10s

# Start subscriber client. Using loop_start() instead of loop_forever() as it's non-blocking.
try:
    sub_client.loop_start()
except:
    print("Something went wrong when starting subscriber lopp")
    sub_client.disconnect()


# Subscriber Code End
# --------------------------------------------------------------------



# --------------------------------------------------------------------
# Timer related start

# to save the elapsed time between on and off while the motor is running
total_run_time = 0.0
# Creating timer object t
t = Timer()

# Timer related end
# --------------------------------------------------------------------




# --------------------------------------------------------------------
# API Endpoints start

@get("/")
def base_endpoint():
    """
    Method: GET

    Base endpoint to test if the API is running or not.

    * Arguments/Parameters: None
    * Output: Python Dict -> Returns JSON automatically upon invoke by Bottle. Retrurns bool value True if API is running correctly.
    """

    return {"API Working": True}


@put("/power/<state>")
def power_toggle(state):
    """_summary_

    Args:
        state (String): Takes a String parameter 'on' or 'off'. This is automatically passed from the dynamic URL.

    Returns:
        _type_: _description_
    """

    power_status = state.lower()
    global total_run_time # using the global variable

    if client.connect(server_ip_address, port=1883, keepalive=60) != 0:
        print("Could NOT connect to broker")
        return {"Power Toggle Success": False}
    
    topic = 'cmnd/washer/Power'
    
    if power_status == 'on':
        client.publish(topic, payload=power_status,qos=0)
        client.disconnect()
        t.start() # start the timer as the device is on

        return {'Power On': True}
    if power_status == 'off':
        client.publish(topic, payload='off', qos=0)
        client.disconnect()
        total_run_time = t.stop() # stopping the timer as the device is off and returning the time in seconds

        return {'Power Off': True}
    else:
        return {"wrong url parameter provided": power_status}


@get('/power/status')
def get_socket_power_status():
        
    if client.connect(server_ip_address, 1883, 60) != 0:
        print("Could NOT connect to broker")
        return {'success': False}

    topic = "cmnd/washer/Power"

    client.publish(topic, '', 0) # Publishes request to get socket power status
    client.disconnect() # disconnects the broker client from the server

    #wait for the message to be appended
    time.sleep(2)
    # Extracting current power status from the MQTT return msg
    curret_power_status = power_toggle_status[-1]["POWER"]
    # Clearing up the power toggle status list after getting current status
    power_toggle_status.clear()
    return {'current_power_status': curret_power_status}


@get('/power/consumption')
def power_consumption():
    time.sleep(3)
    data = sensor_energy_reading[-10:]

    for energy in reversed(data):
        if energy["ENERGY"]["Voltage"] > 0 and energy['ENERGY']['Current'] > 0:
            voltage = float(energy["ENERGY"]["Voltage"])
            amp = float(energy['ENERGY']['Current'])
            watt = voltage * amp
            duration = total_run_time/(60*60) # converting seconds to hours
            energy_consumption = round((watt * duration)/1000, 5)
            sensor_energy_reading.clear()

            # return {"energy consumption in kWh": energy_consumption}
            return {f"energy consumption for {round(total_run_time)}s in kWh": energy_consumption}


# API Endpoints end
# --------------------------------------------------------------------


# Running the API
if __name__ == '__main__':
    run(host='0.0.0.0', port=8080, reloader=True, debug=True)