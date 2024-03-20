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
    """
    Timer class created for extracting time duration between on and off state of the power socket
    """
    def __init__(self):
        self._start_time = None

    def start(self):
        """Start a new timer"""
        if self._start_time is not None:
            raise TimerError(f"Timer is running. Use .stop() to stop it")

        self._start_time = time.perf_counter()

    def stop(self):
        """Stop the timer, and report the elapsed time in seconds"""
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
# server_ip_address = "192.168.0.105" # local mosquitto broker
server_ip_address = "131.159.6.111" # lab mqtt broker

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
    """Defines what action needs to be done when a message is received from the subscribed topic.
    Used as a callback function. When a message is received from the subscribed topic, it loads as a JSON object.
    Then, the object is appended to either one of the list named power_toggle_status or sensor_energy_reading based on
    if it's coming from stat or tele subscribed channel. 
    * States like Power On/Off is appended to power_toggle_status list
    * Telemetry data is saved to sensor_energy_reading list.
    
    If the any of the list size becomes greater than 50, only the last 50 subscribed message that are received are kept.


    Args:
        client (_type_): none
        userdata (_type_): non
        msg (_type_): message received from the mqtt broker for subscribed topics.
    """
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
    HTTP Method: GET
    Endpoint: /

    Base endpoint to test if the API is running or not.

    * Arguments/Parameters: None
    * Output: Python Dict -> Returns JSON automatically upon invoke by Bottle. Retrurns bool value True if API is running correctly.
    """

    return {"API Working": True}


@put("/power/<state>")
def power_toggle(state):
    """
    HTTP Method: PUT
    Endpoint: /power/<state>
    Dynamic Endpoint.

    This endpoint is used to turn on or off the power socket.
    * If user calls the endpoint '/power/on', then the function will publish a message to the MQTT broker causing the switch to turn on.
    * If user calls the endpoint '/power/off', then the function will publish a message to the MQTT broker causing the switch to turn off.
    * If any other value is passed from the URL endpoint, it will return a JSON object notifying the URL endpoint was wrong.
    
    Args:
        state (String): Takes a String parameter 'on' or 'off'. This is automatically passed from the dynamic URL.

    Returns:
        _type_: JSON object
    """

    power_status = state.lower() # for avoiding capitalization error from the URL
    global total_run_time # using the global variable

    if client.connect(server_ip_address, port=1883, keepalive=60) != 0:
        print("Could NOT connect to broker")
        return {"Power Toggle Success": False}
    
    topic = 'cmnd/washer/Power'
    
    if power_status == 'on':
        client.publish(topic, payload=power_status,qos=0)
        client.disconnect()
        t.start() # start the timer as the device is on

        return {'Power On': True} # now the socket is turned on
    if power_status == 'off':
        client.publish(topic, payload='off', qos=0)
        client.disconnect()
        total_run_time = t.stop() # stopping the timer as the device is off and returning the time in seconds

        return {'Power Off': True} # now the socket is turned off
    else:
        return {"wrong url parameter provided": power_status}


@get('/power/status')
def get_socket_power_status():
    """
    HTTP Method: GET
    Endpoint: /power/status

    * This method returns the current status of the power socket to know if it's on or off

    Returns:
        _type_: JSON object with Socket Power Status: ON or OFF
    """
    if client.connect(server_ip_address, 1883, 60) != 0:
        print("Could NOT connect to broker")
        return {'success': False}

    topic = "cmnd/washer/Power"

    client.publish(topic, '', 0) # Publishes request to get socket power status
    client.disconnect() # disconnects the broker client from the server

    # wait for the message to be appended for safety
    time.sleep(2)

    # Extracting current power status from the MQTT return msg
    curret_power_status = power_toggle_status[-1]["POWER"]

    # Clearing up the power toggle status list after getting current status
    power_toggle_status.clear()
    return {'current_power_status': curret_power_status}


@get('/power/consumption')
def power_consumption():
    """HTTP Method: GET
    Endpoint: /power/consumption

    Returns the power usage of the motor or appliances from the time it was started (socket switched on) and when it was switched off (socket switched off)

    * MQTT socket returns power telemetry data at 10s interval (can NOT go lower than 10s).
    * Thus, only an approximation of power usage can be reported.

    The function waits for 3s in the beginning to get any new upcoming telemetry data from the power socket.

    After that, in the variable named 'data', a sliced list with the last 10 entries of the telemetry data from sensor_energy_reading list is created.
    
    Then the list is iterated in reverse to traverse from the last energy data that was received.

    When a device is using power, the MQTT telemetry will return Voltage and Current value greater than 0.

    One assumption was considered that is, the motor's voltage and current usage is consistent all the time.

    * How energy was calculated
    1. We reverse iterate over the sensor telemetry data and try to find the entry that has both voltage and current value greater than 0, meaning the motor is running.

    2. After that, we extract the voltage and current data from the reading and calculated watt = voltage * amp

    3. The duration the motor remained powered on was calculated when the socket was powered off (/power/off endpoint was called)

    4. The duration was calculated in seconds. To return power usage in kWh, we convert the duration seconds into hours format in the duration variable.

    5. The power in kWh is calculated by multiplying (watt * duration) and then dividing by 1000.

    6. After energy consumption was calulated, the sensor_energy_reading list is cleared off to save memory.

    Returns:
        _type_: JSON object with Energy consumption of the motor in kWh and how many seconds the motor was powered on.
    """
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
            return [{"time": f"{round(total_run_time)}", "energy": {energy_consumption}}]
            # return {f"energy consumption for {round(total_run_time)}s in kWh": energy_consumption}


# API Endpoints end
# --------------------------------------------------------------------


# Running the API
if __name__ == '__main__':
    run(host='::', port=3799, reloader=True, debug=True)