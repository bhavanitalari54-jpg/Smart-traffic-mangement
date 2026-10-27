# Smart Traffic Management & Accident Detection System

A full-stack web application for real-time traffic monitoring and heuristic-based accident detection using Python, OpenCV, YOLOv8, Flask, and Socket.IO.

---

## ⚠️ Important Disclaimers

- All **accident detections** are labeled **"Suspected"** and require **human review** before any emergency response.
- **Signal timing recommendations** are **advisory only** and are **not connected to physical traffic signal hardware**.
- The accident detection module uses heuristic computer-vision techniques (frame-difference, bounding-box overlap, stationary-vehicle detection), not a trained deep-learning classifier.

---

## 📦 Features

| Feature | Description |
|---|---|
| Vehicle Detection | YOLOv8n detects cars, trucks, buses, motorcycles with bounding box overlay |
| Traffic Density | Classifies density as LOW / MEDIUM / HIGH per camera |
| Signal Advisory | Recommends green/yellow/red timings based on density |
| Accident Detection | 3-stage heuristic: motion anomaly, bbox overlap, stationary vehicle |
| Live Dashboard | Real-time charts, stats, alerts via WebSocket (Socket.IO) |
| Accident Alerts | Confirm / Dismiss workflow with snapshot images |
| Interactive Map | Google Maps with camera and accident markers |
| History & Reports | Filterable table + CSV export |
| Firebase | Optional Firestore persistence (mock mode if not configured) |

---

## 🗂️ Project Structure

```
traffic/
├── app.py                    ← Flask entry point
├── config.py                 ← All configuration
├── requirements.txt
├── README.md
│
├── modules/
│   ├── vehicle_detector.py   ← YOLOv8n wrapper
│   ├── traffic_analyzer.py   ← Density + signal logic
│   ├── accident_detector.py  ← Heuristic accident detection
│   ├── alert_manager.py      ← Alert lifecycle + Socket.IO push
│   └── video_processor.py    ← Background video thread
│
├── database/
│   └── firebase_manager.py   ← Firestore CRUD (graceful mock fallback)
│
├── static/
│   ├── css/style.css
│   └── js/  dashboard.js  charts.js  alerts.js  map.js
│
├── templates/
│   ├── base.html  login.html  dashboard.html  monitoring.html
│   ├── accidents.html  signals.html  map.html  history.html  settings.html
│
└── samples/
    ├── generate_samples.py   ← Generates demo traffic videos
    ├── traffic1.mp4          ← Auto-generated sample (after running generator)
    └── traffic2.mp4
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10 or newer
- pip

### 2. Clone / unzip the project

```bash
cd traffic
```

### 3. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

> YOLOv8n weights (`yolov8n.pt`) download automatically on first run (~6 MB).

### 5. Generate sample traffic videos

```bash
python samples/generate_samples.py
```

This creates `samples/traffic1.mp4` and `samples/traffic2.mp4` — synthetic videos with moving vehicle rectangles.

### 6. Run the application

```bash
python app.py
```

Open your browser at: **http://localhost:5000**

### 7. Login

| Username | Password |
|---|---|
| `admin` | `traffic123` |

---

## ⚙️ Configuration

Edit **`config.py`** to customise:

| Setting | Description |
|---|---|
| `DEMO_USERNAME / DEMO_PASSWORD` | Login credentials |
| `GOOGLE_MAPS_API_KEY` | Google Maps API key (or set `GOOGLE_MAPS_KEY` env var) |
| `FIREBASE_CREDENTIALS_PATH` | Path to `firebase_credentials.json` |
| `CAMERAS` | List of camera sources (video file, RTSP URL, or webcam index) |
| `YOLO_CONFIDENCE` | Detection confidence threshold (default 0.50) |
| `DENSITY_LOW_MAX / DENSITY_MEDIUM_MAX` | Vehicle count thresholds |
| `SIGNAL_TIMINGS` | Green/Yellow/Red timing per density level |
| `PROCESS_EVERY_N_FRAMES` | CPU saver: process 1 in every N frames |

### Environment Variables (override config.py)

```bash
export SECRET_KEY="your-secret-key"
export GOOGLE_MAPS_KEY="AIza..."
export FIREBASE_CREDENTIALS="/path/to/firebase_credentials.json"
```

---

## 📷 Connecting a Live Camera

To use a **webcam**:
```python
# In config.py, set source to webcam index
"source": 0   # first webcam
```

To use an **IP camera / RTSP stream**:
```python
"source": "rtsp://username:password@192.168.1.100:554/stream"
```

To use a **video file**:
```python
"source": "/path/to/your/traffic.mp4"
```

The system loops video files automatically, so sample videos play continuously.

---

## 🔥 Firebase Setup (Optional)

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a project → Project Settings → Service Accounts → Generate new private key
3. Save the JSON file as `traffic/firebase_credentials.json`
4. The system will automatically detect and use it

**Without Firebase**, the system runs in **mock mode** — all data is stored in memory and lost on restart, but the UI works fully.

---

## 🗺️ Google Maps Setup (Optional)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable **Maps JavaScript API**
3. Create an API key and restrict it to your domain
4. Set `GOOGLE_MAPS_API_KEY` in `config.py` or via environment variable

**Without a key**, the map page shows a placeholder with camera coordinates listed as text.

---

## 🧪 Testing Individual Modules

```bash
# Smoke-test vehicle detector
python -m modules.vehicle_detector

# Smoke-test accident detector
python -m modules.accident_detector

# Smoke-test traffic analyzer
python -m modules.traffic_analyzer

# Generate sample videos
python samples/generate_samples.py
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask 2.3+, Flask-SocketIO 5.3+ |
| Computer Vision | OpenCV 4.8+, Ultralytics YOLOv8n |
| Frontend | HTML5, Vanilla CSS (glassmorphism), JavaScript |
| Real-time | Socket.IO (WebSocket) |
| Charts | Chart.js 4.x |
| Maps | Google Maps JavaScript API |
| Database | Firebase Firestore (optional) |
| Fonts | Google Fonts — Inter, JetBrains Mono |

---

## 🔒 Security Notes

- Change `SECRET_KEY` before deploying anywhere beyond localhost
- Replace demo credentials with a proper authentication system for production
- Restrict the Google Maps API key to your domain
- Do not commit `firebase_credentials.json` to version control — add it to `.gitignore`

---

## 📄 License

This project is provided for educational and demonstration purposes.
All accident detection outputs are heuristic estimates — not reliable enough for real-world emergency dispatch without significant additional validation and testing.
