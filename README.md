# Praktikum - Cocktail Mixer Glass Washing

## i. Overview
This repository contains the codes and architecture and detailed description for the Praktikum of Human Software Mediator Pattern.

*This repository is for the Cocktail Mixer's Glass Washing part*.

There are two main parts for the tasks.
1. A REST API server (Socket Server referred to from onwards) to turn an MQTT Enable Power Socket On/Off to switch on the DC Water Pump and also return the Power Usage of a wash cycle
2. Using the Process Engine to Integrate the above REST API and also control the Robot Movement to wash multiple glasses in a row.

![Simple Architecture of the Glass Washing Mechanism](img/overall_architecture_1.png)

*Picture: Simple Architecture of the Overall workflow of the tasks*

## ii. Detailed Architectrue of the two main parts

### 1. Socket Server REST API & MQTT Pub/Sub Architecture for Power Socket and Socket Server

> **TL;DR**: Using the Socket Server REST API endpoints, the Process Engine can later on turn the Delock Power Socket on or off. Socket Server can also return the power usage data in kWh for each time the water pump motor was used from the sensor telemetry data of the power socket to the Process Engine.

This is a REST API server used to control the [Delock WLAN Power Socket Switch MQTT with energy monitoring](http://https://www.delock.com/produkt/11827/merkmale.html "Delock WLAN Power Socket Switch MQTT with energy monitoring"). The WLAN socket supports [MQTT Protocol](https://mqtt.org/ "MQTT Protocol"). The API was implemented using [Bottle: Python Web Framework](https://bottlepy.org/docs/dev/ "Bottle: Python Web Framework"). It serves as an itermediary medium for the power socket, MQTT Broker Server and the Process Engine.

![Picture of Delock WLAN Power Socket](img/631eff53a09771.36696341.jpg)

*Picture: Delock WLAN Power Socket with MQTT Support*

![Picture of Delock Power Sockets Web UI](img/5ef5a15fa2fd46.98572189.jpg)

*Picture: Delock Power Socket Web UI*


Using various endpoints of this API and through MQTT protocol, the socket:
1. Can be turned **ON** or **OFF**
2. Can provide current **Power Status** of the switch (on or off)
3. Can provide **Telemetry Data** from socket sensors (voltage, watts, total power usage etc).

#### a. Installation & Running the API Server

- Clone the repository from Github
- Create a Virtual Environment using:
`python3 -m venv .venv`
- Activate the Virtual Environment using:
`source .venv/bin/activate`
- Install required dependencies by running the following code:
`python3 -m pip install -r requirements.txt`
- The source code is saved in `/src` directory.
- Run the API server using:
`python3 src/washer_api.py`
- The server will be listening to incoming request from *IPV4* and *IPV6* as well on the custom port *3799*.

#### b. API Endpoints Overview

| Endpoint           | HTTP Method | URL Routing Type | URL Arguments | Usage                                                         | Example Return                                 |
|--------------------|-------------|------------------|---------------|---------------------------------------------------------------|------------------------------------------------|
| /                  | GET         | Static           | None          | To check if the API server is running                         | {"API Working": True}                          |
| /power/{state}     | PUT         | Dynamic          | on            | To turn on the power socket                                   | {'Power On': True}                             |
| /power/{state}     | PUT         | Dynamic          | off           | To turn off the power socket                                  | {'Power Off': True}                            |
| /power/status      | GET         | Static           | None          | To check if the socket is turned on/off                       | {'current_power_status' : curret_power_status} |
| /power/consumption | GET         | Static           | None          | Return the power consumption usage each time the motor was on | {"energy consumption for 14s in kWh": 0.00034} |


#### c. API Endpoints Short Explanations

For the **Process Engine**, *endpoints 2 and 4 *were invoked. Rest are for testing purposes.

**1. "/"**
- Base Endpoint.
- To test if the API is running or not
- **Output**: *Python Dict -> Returns JSON* automatically upon invoke by Bottle. Retrurns bool value True if API is running correctly.
- Refer to code documentations for implementation logics.

**2. "/power/{state}"**
- Uses dynamic routing. {state} part needs to be replaced with "on" or "off".
- MQTT Broker server for topic publishing and subscribing is provided by the lab and it listens to standard MQTT Port 1883.
- If user calls the endpoint **'/power/on'**, then the function will publish a message to the MQTT broker causing the switch to *turn on*.
	- The Socket Server publishes to the topic `'cmnd/washer/Power'` to the MQTT Broker Server (using lab's MQTT Broker Server) with the correct payload.
	- The Power socket is subscribed to the same topic and once it receives the published message, it turns itself on.
	- QOS (Quality of Service) is by default 0.
- If user calls the endpoint **'/power/off'**, then the function will publish a message to the MQTT broker causing the switch to *turn off*.
	- The Socket Server publishes to the topic `'cmnd/washer/Power'` to the MQTT Broker Server with the correct payload.
	- The Power socket is subscibed to the same topic and once it receives the published message, it turns itself off.
	- QOS (Quality of Service) is by default 0.
- If any other value is passed from the URL endpoint, it will return a JSON object notifying the URL endpoint was wrong.
- Refer to code documentations for implementation logics.

**3. "/power/status"**
- This method returns the current status of the power socket to know if it's on or off
- Refer to code documentations for implementation logics in details.

**4. "/power/consumption"**

- Returns the power usage of the motor or appliances from the time it was started (socket switched on) and when it was switched off (socket switched off)
- MQTT socket returns power telemetry data at 10s interval (can NOT go lower than 10s).
- Thus, only an approximation of power usage can be reported.
- Returns energy usage in kWh.
- How energy consumption was calculated:
	- The voltage and current data from the reading and calculated as *watt = voltage * amp*
	- The duration the motor remained powered on was calculated when the socket was powered off (/power/off endpoint was called)
	- The duration was calculated in seconds.
	- To return power usage in kWh, the duration in seconds was converted to hours.
	- The power in kWh is calculated by multiplying *(watt * duration)* and then dividing by 1000.
- Refer to code documentations for implementation logics in details.

#### d. MQTT Publish/Subscribe Architecture

The WLAN power socket that is being used supports MQTT protocol. This protocol uses the Publish/Subscribe architecture.

We have a server that runs the MQTT Broker Server (provided by praktikum lab) which was used to publish and subscribe to messages. The Socket Server serves as both:
- A **publisher** client (publishes to command topic to turn the socket on or off or get status) 
- A **subscriber** client (subscribes to telemtry topic or status topic of the switch to get sensor telemetry data or power status data)

The Delock Power Socket also serves as a client and subscribes to and publishes to topics. Below an architecture of how publishing and subscribing to topics is done for the power socket case is given below.


![Architecture of MQTT Architecture](img/MQTT%20Architecture.drawio.png)

*Picture: MQTT Pub/Sub Architecture used in this project*

**Example Scenario:**
When the Socket Server client publishes a Message to the topic `cmnd/washer/Power` with appropriate payload while the Delock power socket had already been subscribed to the same topic and upon receiving the message, it turns the power on or off or publishes the current status of the power socket whether it's on or off to the topic `stat/washer/RESULT`.

The Socket Server client also subcribes to topic for example `stat/washer/RESULT` and receives message when the power socket publishes any message.
