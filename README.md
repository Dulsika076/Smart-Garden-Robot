#  🌱 Smart Garden Robot - Automated Plant Monitoring, AI Weed Detection & Irrigation System

## Problem Statement

Small-scale plant care, home gardening, and pot-based agriculture often depend on manual observation for watering, soil condition checking, and plant health monitoring. This process is time-consuming, inconsistent, and difficult to scale when multiple plants must be monitored individually.

Traditional plant monitoring systems usually measure only one environmental parameter or require fixed sensor installation for every plant. They often do not combine soil moisture analysis, weed detection, plant health monitoring, and automatic irrigation into one complete workflow.

Our project, **Smart Garden Robot**, addresses this gap by developing an automated robot-based plant monitoring system that moves from pot to pot, reads soil and environment data, detects weed/plant health using AI, uploads all results to a live web dashboard, and controls a water pump based on the required moisture level.

The goal is to create a smart, low-cost, and scalable system that can monitor each plant individually and support automated watering decisions.

---

## Project Overview

The **Smart Garden Robot** is an integrated system that combines:

- Robot movement and pot detection
- Soil moisture sensing
- Temperature and humidity monitoring
- CD4051 multiplexer-based sensor selection
- LabVIEW + DAQ-based data acquisition
- Python-based weed and plant health detection
- Lovable AI web dashboard
- ESP32-based water pump control
- Real-time data upload using API endpoints

The robot moves to each pot, stops using IR-based detection, identifies the current pot using binary signals, measures the selected soil moisture sensor through a multiplexer, and sends the processed data to the website.

A separate AI vision module processes plant images to detect weed presence and plant/leaf health. The website displays both sensor-based data and AI-based analysis in one dashboard.

---

## System Architecture

The system operates as a multi-module architecture:

```text
[ Robot Movement System ]
Arduino + Motor Driver + IR Sensor
START / NEXT control logic
Pot stop detection
Binary pot ID output
        |
        | STOP + BIT0 + BIT1
        v
[ NI DAQ + LabVIEW System ]
Analog sensor reading
Digital robot signal reading
Moisture percentage calculation
Soil condition classification
Pump duration calculation
JSON API upload
        |
        | HTTP POST
        v
[ Lovable Web Dashboard ]
Live environment display
Pot-wise sensor data
AI weed/health results
Pump control interface
        |
        | Pump command
        v
[ ESP32 Pump Controller ]
Wi-Fi command receiving
Relay switching
Water pump ON/OFF control
```

Additional AI module:

```text
[ Python AI Vision System ]
Camera/Image input
Weed detection
Plant health/leaf condition detection
Confidence score
        |
        | HTTP POST
        v
[ Lovable Web Dashboard ]
```

---

## Main Features

- Automatic robot movement between pot plants
- IR-based stop detection at each pot
- Binary pot identification using Arduino digital outputs
- Soil moisture sensor selection using CD4051 multiplexer
- DAQ-based analog and digital signal acquisition
- LabVIEW-based moisture, temperature, and humidity processing
- Soil condition classification: Dry, Moderate, Wet
- Recommended pump duration calculation: 0s, 2s, 4s, or 8s
- Real-time website dashboard
- Python AI-based weed detection
- Plant health and leaf condition monitoring
- ESP32 relay-based water pump control
- Modular design with separate robot, LabVIEW, AI, website, and pump systems

---

## Hardware Components

| Component | Purpose |
| --- | --- |
| Arduino | Robot movement control and pot signal generation |
| Motor Driver | Controls robot motors |
| IR Sensor | Detects pot stopping positions |
| NI DAQ Card | Reads analog sensor signals and digital robot signals |
| Soil Moisture Sensors | Measures moisture level of each pot |
| CD4051 Multiplexer | Selects one moisture sensor output using binary input |
| Temperature Sensor | Measures surrounding/environment temperature |
| Humidity Sensor | Measures humidity level |
| ESP32 | Receives pump commands from website |
| Relay Module | Switches water pump ON/OFF |
| Water Pump | Provides irrigation to selected pot |
| Camera / Laptop | Captures plant images for AI detection |

---

## Software & Tools

| Tool / Platform | Role |
| --- | --- |
| LabVIEW | Sensor processing, DAQ reading, JSON generation, website upload |
| NI DAQ Assistant | Analog and digital signal acquisition |
| Arduino IDE | Robot movement and signal output programming |
| Python | AI image processing and plant analysis upload |
| Lovable AI | Web dashboard and API endpoint development |
| ESP32 Web Server / Wi-Fi | Pump control through HTTP commands |
| GitHub | Code, simulation, and project documentation |

---

## Robot Signal Logic

The robot Arduino sends three digital signals to the DAQ card:

| Arduino Signal | DAQ Input | Meaning |
| --- | --- | --- |
| D7 | P0.0 | Robot Stop Signal |
| D8 | P0.1 | Pot Bit 0 |
| D9 | P0.2 | Pot Bit 1 |

### Pot Identification Table

| Robot State | STOP | BIT1 | BIT0 | Binary | Pot |
| --- | ---: | ---: | ---: | --- | --- |
| Moving | 0 | 0 | 0 | 00 | No reading |
| Stopped at Pot 1 | 1 | 0 | 1 | 01 | Pot 1 |
| Stopped at Pot 2 | 1 | 1 | 0 | 10 | Pot 2 |
| Stopped at Pot 3 | 1 | 1 | 1 | 11 | Pot 3 |

LabVIEW calculates the pot number using:

```text
Pot ID = BIT1 x 2 + BIT0
```

Pot data is uploaded only when the stop signal changes from `0` to `1`.

```text
New Stop Event = Current STOP AND NOT Previous STOP
```

This prevents repeated uploading while the robot remains stopped.

---

## CD4051 Multiplexer Connection

The CD4051 multiplexer is used to connect multiple soil moisture sensors to one DAQ analog input.

```text
Pot 1 Soil Sensor Output -> CD4051 Channel 1
Pot 2 Soil Sensor Output -> CD4051 Channel 2
Pot 3 Soil Sensor Output -> CD4051 Channel 3

CD4051 Common Output / SIG / Z -> DAQ AI0
```

### Multiplexer Select Pins

| CD4051 Pin | Connected To |
| --- | --- |
| S0 / A | Arduino D8 / Pot Bit 0 |
| S1 / B | Arduino D9 / Pot Bit 1 |
| S2 / C | GND |
| EN / INH | GND |
| VCC | 5V |
| GND / VSS | GND |
| VEE | GND |

The same binary output from Arduino selects both the correct pot number and the correct soil moisture sensor.

---

## LabVIEW System

LabVIEW is responsible for:

1. Reading analog sensor values from DAQ
2. Reading robot stop and pot ID signals
3. Calculating moisture percentage
4. Calculating temperature and humidity
5. Classifying soil condition
6. Calculating recommended pump duration
7. Sending JSON data to the web dashboard

### Analog DAQ Inputs

| DAQ Channel | Signal |
| --- | --- |
| AI0 | Selected soil moisture voltage from CD4051 |
| AI1 | Temperature sensor voltage |
| AI2 | Humidity sensor voltage |

### Digital DAQ Inputs

| DAQ Digital Input | Signal |
| --- | --- |
| P0.0 | Robot Stop Signal |
| P0.1 | Pot Bit 0 |
| P0.2 | Pot Bit 1 |

---

## Moisture Calculation

The soil moisture voltage is converted into moisture percentage using calibration values.

```text
Moisture % = ((Vdry - Vsoil) / (Vdry - Vwet)) x 100
```

Where:

- `Vdry` = sensor voltage in dry soil
- `Vwet` = sensor voltage in wet soil
- `Vsoil` = selected soil voltage from multiplexer

The result is limited between 0% and 100%.

---

## Soil Condition & Pump Duration Logic

| Moisture Level | Soil Condition | Pump Duration |
| --- | --- | --- |
| Below 25% | Dry | 8 seconds |
| 25% - 40% | Dry | 4 seconds |
| 40% - 60% | Moderate | 2 seconds |
| Above 60% | Wet | 0 seconds |

The pump duration is sent to the website as a recommendation. The pump can then be controlled through the ESP32.

---

## Website Dashboard

The web dashboard is built using **Lovable AI**.

The dashboard displays:

- Live temperature
- Live humidity
- Selected pot ID
- Soil moisture percentage
- Selected soil voltage
- Soil condition
- Recommended pump duration
- Weed detection status
- Plant health status
- Leaf condition
- Confidence percentage
- Pump command status
- Last updated time

---

## API Endpoints

### 1. Environment Data

LabVIEW sends temperature and humidity continuously.

```http
POST /api/public/environment
```

Example JSON:

```json
{
  "temperature": 30.2,
  "humidity": 68.5
}
```

### 2. Pot Reading Data

LabVIEW sends pot data only when the robot stops at a pot.

```http
POST /api/public/pot-reading
```

Example JSON:

```json
{
  "potId": 1,
  "moisture": 35.4,
  "selectedSoilVoltage": 2.15,
  "temperature": 30.2,
  "humidity": 68.5,
  "soilCondition": "Dry",
  "recommendedPumpDuration": 4
}
```

### 3. Plant Analysis Data

Python AI system sends weed and plant health results.

```http
POST /api/public/plant-analysis
```

Example JSON:

```json
{
  "potId": 1,
  "weedDetected": "Yes",
  "plantHealth": "Warning",
  "leafCondition": "Yellow",
  "diseaseName": "Possible nutrient deficiency",
  "confidence": 87.3,
  "imageUrl": ""
}
```

### 4. Pump Control

The website sends pump duration command to the ESP32.

```text
http://ESP32_IP/pump?duration=DURATION
```

Example:

```text
http://192.168.4.1/pump?duration=4
```

The ESP32 switches the relay ON, runs the pump for the selected duration, and switches it OFF automatically.

---

## AI Weed & Plant Health Detection

The AI vision module runs separately on a laptop using Python.

The process:

```text
Capture plant image
        |
        v
Python image processing / AI model
        |
        v
Detect weed status
Detect leaf/plant health
Calculate confidence score
        |
        v
Upload result to website API
```

The website combines this AI result with the corresponding pot sensor data.

---

## Complete Working Flow

```text
1. User presses START.
2. Robot moves toward Pot 1.
3. IR sensor detects stop marker.
4. Robot stops.
5. Arduino sends STOP + binary pot ID to DAQ.
6. Arduino binary bits also select the correct CD4051 moisture channel.
7. DAQ reads selected soil voltage.
8. LabVIEW calculates moisture percentage.
9. LabVIEW classifies soil condition.
10. LabVIEW calculates recommended pump duration.
11. LabVIEW uploads pot data to website.
12. Python AI uploads weed and plant health result.
13. Website displays all data in real time.
14. User runs pump or uses recommended pump duration.
15. Website sends pump command to ESP32.
16. ESP32 activates relay and runs water pump.
17. Robot moves to next pot after OK/NEXT command.
```

---

## Simulation & Development Progress

The project development was completed through multiple simulation and testing stages. The GitHub commit history includes:

- LabVIEW front panel design
- DAQ analog input simulation
- DAQ digital input simulation
- Robot stop and pot ID logic
- Moisture calculation logic
- Soil condition and pump duration logic
- JSON cluster formatting
- Website API integration
- Multiplexer sensor selection planning
- ESP32 pump command testing
- AI plant analysis API integration

---

## Repository Structure

```text
Smart-Garden-Robot/
|
+-- Arduino/
|   +-- robot_movement/
|   +-- esp32_pump_control/
|
+-- LabVIEW/
|   +-- front_panel_screenshots/
|   +-- block_diagram_screenshots/
|   +-- simulation_files/
|
+-- Python_AI/
|   +-- weed_detection/
|   +-- plant_health_analysis/
|   +-- api_upload/
|
+-- Website_API/
|   +-- api_examples/
|   +-- json_payloads/
|
+-- Hardware/
|   +-- wiring_diagrams/
|   +-- cd4051_multiplexer_connection/
|   +-- sensor_connections/
|
+-- Documentation/
|   +-- system_architecture.md
|   +-- testing_procedure.md
|   +-- final_report.md
|
+-- README.md
```

---

## Testing Procedure

### DAQ Signal Test

1. Connect Arduino D7, D8, D9 to DAQ digital inputs.
2. Check Moving state gives `000`.
3. Check Pot 1 gives `101` for STOP, BIT1, BIT0.
4. Check Pot 2 gives `110`.
5. Check Pot 3 gives `111`.
6. Confirm LabVIEW displays correct pot number.

### Multiplexer Test

1. Connect Pot 1 sensor to CD4051 Channel 1.
2. Connect Pot 2 sensor to CD4051 Channel 2.
3. Connect Pot 3 sensor to CD4051 Channel 3.
4. Change Arduino binary output.
5. Confirm DAQ AI0 reads the correct selected sensor voltage.

### Website Test

1. Send fixed environment JSON.
2. Confirm temperature and humidity update.
3. Send fixed pot-reading JSON.
4. Confirm pot ID, moisture, soil condition, and pump duration update.
5. Send AI plant-analysis JSON.
6. Confirm weed and plant health result appears.

### Pump Test

1. Connect ESP32 to Wi-Fi.
2. Connect relay and pump.
3. Send pump command from website.
4. Confirm pump turns ON.
5. Confirm pump turns OFF after selected duration.

---

## Final Outcome

The final system demonstrates a complete smart agriculture prototype that combines robotics, sensor acquisition, AI analysis, IoT communication, and automated irrigation control.

The project successfully shows how a mobile robot can monitor multiple pot plants individually, send real-time data to a website, detect plant health issues, and support automatic watering decisions using a connected ESP32 pump controller.

---

## Future Improvements

- Add automatic navigation instead of manual OK/NEXT control
- Add database history for each pot
- Add mobile notification for dry soil or unhealthy plants
- Improve AI model accuracy using more plant image datasets
- Add solar-powered robot operation
- Add automatic weed removal mechanism
- Add multiple plant rows and larger field support

---

## Keywords

`Smart Garden Robot` `LabVIEW` `NI DAQ` `Arduino` `ESP32` `IoT` `Python` `AI` `Computer Vision` `Weed Detection` `Plant Health Monitoring` `Soil Moisture` `CD4051 Multiplexer` `Automation` `Smart Agriculture`

