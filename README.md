# The Di-Hydro Visualization Tool

## IF YOU ARE AN OPERATOR/USER, PLEASE READ THE "Visualization Tool USER MANUAL.docx" file, inside the main folder!!!


# IMPORTANT NOTICE!

  # Getting the files from Github run this in the terminal:

    git clone https://github.com/TheoN03/The-Di-Hydro-Visualization-Tool


    If the .exe file does not work after cloning the repository, double click the <build_installer.bat> file and it will reinstall everything.
    After this step, go to <dist> folder, then to <The Di-Hydro Visualization Tool> folder and open the VT by opening <The Di-Hydro Visualization Tool.exe> file.

## Overview

The Di-Hydro Visualization Tool is a realtime industrial monitoring and Augmented Reality (AR) visualization platform designed for:

* Hydropower plant parameter monitoring
* Digital Twin visualization
* AE Sensors monitoring
* Realtime JSON telemetry visualization
* CSV / Excel industrial dataset playback
* RTSP AR camera overlay
* MQTT / Mosquitto integration for external partner data streams

The application provides:

* Animated realtime graphs
* Hover timestamp inspection
* Pre-alert and alert warning system
* AR-style HUD visualization
* JSON sequential playback
* Semi-transparent guided help overlays
* Camera-assisted AR mode
* Multi-tab industrial visualization workflow

---

# Main Features

## Tab 1 - PPC Parameters Dashboard

Main industrial monitoring dashboard.

### Supports:

* CSV files
* Excel files (.xlsx / .xls)
* JSON folders with sequential telemetry snapshots

### Includes:

* 9 realtime parameter cards
* Warning and alert thresholds
* 20-value rolling graphs
* Hover timestamps
* Warning lights
* Acknowledge / CLEAR buttons
* Guided overlay help system

### Typical Data Sources

* Generator monitoring
* Turbine monitoring
* Cooling systems
* Thermal systems
* Digital twin process parameters

---

## Tab 2 - Augmented Reality (AR) Visualization Dashboard

Realtime AR/HUD style visualization environment.

### Subsections

* Generator
* Turbine
* AE Sensors
* Digital Twin

### Supports

* JSON folder playback
* RTSP camera overlay
* Realtime parameter rendering
* Animated warnings
* 3D interactive graphs

### JSON Logic

The system automatically:

1. Detects parameter names
2. Detects units
3. Detects timestamps
4. Groups data by category
5. Selects the 3 most important distinct parameters

If fewer than 3 distinct parameters exist:

* Remaining sections stay blank

### Supported JSON Example

```json
{
    "name": "{'type': 'Property', 'value': 'Acceleration X'}",
    "measurement": "{'type': 'Property', 'value': 102.0, 'measurementUnit': {'type': 'Property', 'value': 'raw_count'}}",
    "category": "{'type': 'Property', 'value': 'acceleration'}"
}
```

---

# Folder Structure

Recommended project structure:

```text
The Di-Hydro Visualization Tool/
│
├── app.py
├── config/
│   ├── param_name_map.json
│   ├── thresholds.json
│   ├── rtsp_camera_config.json
│   └── mqtt_partner_config.json
│
├── data/
│   ├── partner1/
│   ├── partner2/
│   ├── partner3
│   ├── partner4/
│   └── partner5/
│
├── dist/
├── build/
└── installer/
```

---

# JSON Folder Playback

## How It Works

The software scans all JSON files inside a selected folder.

It automatically:

* Sorts files
* Reads values sequentially
* Creates playback timelines
* Updates graphs every second

## Recommended JSON Organization

```text
data/
└── acceleration/
    ├── sample_0001.json
    ├── sample_0002.json
    ├── sample_0003.json
```

---

# Camera / RTSP Configuration

The AR system supports RTSP cameras.

## Default Configuration

```python
CAM_IP = "192.168.1.30"
USERNAME = "admin"
PASSWORD = "ERFQRH"
```
NOTICE!!! These settings will not work for you. They are just an example. USE YOUR IP & CAMERA CONFIGURATION!

## Runtime Editing

Inside the GUI:

* Open Camera Settings
* Modify:

  * IP
  * Username
  * Password
  * Port
  * Channel

Settings are automatically saved.

---

# Camera Timeout Protection

The software prevents GUI freezing if:

* Camera is disconnected
* RTSP stream fails
* Timeout occurs

Example handled warning:

```text
Stream timeout triggered after 30036 ms
```

The software:

1. Detects timeout
2. Stops connection attempt
3. Displays warning popup
4. Keeps GUI responsive

---

# MQTT / Mosquitto Integration

The software includes:

* Mosquitto launcher
* MQTT subscriber GUI
* Partner connection manager

## Features

* Start Mosquitto broker
* Subscribe to topics
* Save JSON streams locally
* Monitor terminal output

---

# Building the EXE

## Included Build System

The package contains:

* Portable PyInstaller build
* Installer creation scripts
* Automatic virtual environment setup
* Automatic pip repair

## Generated Files

### Main EXE

```text
The Di-Hydro Visualization Tool.exe
```

### Installer

```text
The_Di-Hydro_Visualization_Tool_Setup.exe
```

---

# Building on Windows

## Step 1

Install Python 3.10+.

## Step 2

Open:

```text
build_installer.bat
```

The build system automatically:

* Creates temporary venv
* Repairs pip
* Installs dependencies
* Builds EXE
* Creates installer

---

# Runtime Requirements

The final installed EXE:

* DOES NOT require Python
* DOES NOT require .venv
* DOES NOT require VSCode
* DOES NOT require GitHub

Only the installer build machine needs Python.

---

# Supported Data Types

## Industrial

* Temperature
* Pressure
* Voltage
* Current
* Frequency
* Humidity

## IMU / Sensors

* Acceleration
* Angular Velocity
* Magnetometer
* Orientation
* Analog Voltage

---

# Recommended JSON Priorities

The system prioritizes:

1. Acceleration
2. Gyroscope
3. Magnetometer
4. Orientation
5. Temperature
6. Pressure
7. Humidity

---

# Warning System

## States

### Normal

Green indicator

### Pre-Alert

Orange animated pulse

### Alert

Red animated warning

---

# AR Graph Controls

## Mouse Controls

### Rotate

Left mouse drag

### Zoom

Mouse wheel

### Hover

Displays:

* Value
* Timestamp

---

# Guided Help Overlay

Both tabs contain:

* Semi-transparent overlay
* Arrow explanations
* Interactive walkthrough
* Tab-specific help

---

# GitHub Deployment

The project is fully portable.

---

# Troubleshooting

## Camera Freeze

Problem:

```text
Stream timeout triggered
```

Solution:

* Verify RTSP camera IP
* Verify credentials
* Verify network connectivity

The GUI should remain responsive.

---

## No JSON Parameters Detected

Check:

* JSON syntax
* "measurement.value" exists
* Files contain numeric values

---

## EXE Build Failure

Run:

```text
build_installer.bat
```

The script automatically:

* Repairs pip
* Recreates venv
* Reinstalls dependencies

---

# Credits

Developed by Accent Pro 2000 S.R.L (AP2K). for:

* The DI-HYDRO Project
* Industrial realtime visualization
* Digital Twin monitoring
* Hydropower monitoring
* AR telemetry systems

---
# The Web Dashboard with Analytics for Digital Twin Parameters (Visualization Tool Online Extension)

Link: https://di-hydro-dashboard-digital-twin-2.onrender.com/

Guest Login:
Username: guest@accent.ro
Password: AP2Kguest

This extension provides:

* Browser-based realtime visualization
* AI prediction graphs
* Multi-parameter dashboards
* Editable Digital Twin inputs
* Alert and pre-alert visualization
* Authentication system
* Forecasting and analytics

Based on the uploaded dashboard source code.

---

# Main Features of The Web Dashboard

## Web Dashboard

* Secure login system
* Multi-sheet Excel/CSV loading
* Realtime KPI monitoring
* Hover inspection
* AI forecasting graphs
* Multi-parameter plots
* Editable Digital Twin simulation

## AI Prediction

The dashboard uses:

* GradientBoostingRegressor
* LinearRegression fallback
* Forecast horizon prediction
* Rolling-window analysis

## Alert System

Three operating states:

* OK
* PRE-ALERT
* ALERT

Thresholds are generated automatically from:

* Mean values
* Standard deviation

## Supported Data

* XLSX
* XLS
* CSV
* .JSON

Detected automatically:

* Numeric parameters
* Time columns
* Generator/Turbine/Water zones

# Forecasting Models

Optional pretrained forecasting models:

```text id="i7y5m2"
hydro_forecast_models.joblib
```

If missing:

* automatic fallback forecasting is used

---

# MIT License

Copyright (c) 2026 Accent Pro 2000 S.R.L.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

