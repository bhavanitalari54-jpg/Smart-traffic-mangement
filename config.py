"""
config.py – Central configuration for the Smart Traffic Management System.
Edit this file to point to your Firebase credentials, Google Maps API key,
camera sources, and detection thresholds.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # ─── Flask ───────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get("SECRET_KEY", "traffic-system-demo-secret-2024")
    DEBUG = os.environ.get("DEBUG", "True").lower() == "true"

    # ─── Demo Credentials ────────────────────────────────────────────────────
    DEMO_USERNAME = "admin"
    DEMO_PASSWORD = "traffic123"

    # ─── Firebase ────────────────────────────────────────────────────────────
    # Place your Firebase service-account JSON at this path, or set the env var.
    FIREBASE_CREDENTIALS_PATH = os.environ.get(
        "FIREBASE_CREDENTIALS",
        str(BASE_DIR / "firebase_credentials.json"),
    )
    FIREBASE_ENABLED = os.path.exists(FIREBASE_CREDENTIALS_PATH)

    # ─── Google Maps ─────────────────────────────────────────────────────────
    # Replace with your actual API key (or set GOOGLE_MAPS_KEY env var).
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_KEY", "YOUR_GOOGLE_MAPS_API_KEY")

    # ─── YOLO Model ──────────────────────────────────────────────────────────
    YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolov8n.pt")  # auto-downloaded on first run
    YOLO_CONFIDENCE = 0.50
    # COCO class IDs we care about: car=2, motorcycle=3, bus=5, truck=7
    VEHICLE_CLASS_IDS = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

    # ─── Traffic Density Thresholds ──────────────────────────────────────────
    DENSITY_LOW_MAX = 5        # 0–5   → LOW
    DENSITY_MEDIUM_MAX = 15    # 6–15  → MEDIUM  (>15 → HIGH)

    # ─── Signal Timing Recommendations (seconds) ─────────────────────────────
    SIGNAL_TIMINGS = {
        "LOW":    {"green": 30, "yellow": 5, "red": 25},
        "MEDIUM": {"green": 45, "yellow": 5, "red": 40},
        "HIGH":   {"green": 60, "yellow": 5, "red": 55},
    }

    # ─── Accident Detection ──────────────────────────────────────────────────
    ACCIDENT_MOTION_THRESHOLD = 50      # pixel intensity diff for motion
    ACCIDENT_OVERLAP_IOU = 0.25         # IoU above this → suspected collision
    ACCIDENT_STATIONARY_FRAMES = 40     # frames to declare a vehicle stationary
    ACCIDENT_CONFIDENCE_COOLDOWN = 5.0  # seconds between alerts per camera

    # ─── Video Processing ────────────────────────────────────────────────────
    PROCESS_EVERY_N_FRAMES = 3          # process 1 in every N frames (CPU saver)
    STREAM_FPS = 20                     # target MJPEG stream FPS
    FRAME_WIDTH = 640
    FRAME_HEIGHT = 480

    # ─── Camera Definitions ──────────────────────────────────────────────────
    # source: integer (webcam index), RTSP URL, or path to a video file
    CAMERAS = [
        {
            "id": "cam_001",
            "name": "Main Junction – North",
            "source": str(BASE_DIR / "samples" / "traffic1.mp4"),
            "lat": 28.6139,
            "lng": 77.2090,
            "road": "NH-44 North",
        },
        {
            "id": "cam_002",
            "name": "City Square – East",
            "source": str(BASE_DIR / "samples" / "traffic2.mp4"),
            "lat": 28.6200,
            "lng": 77.2150,
            "road": "Ring Road East",
        },
        {
            "id": "cam_003",
            "name": "Highway Bypass – South",
            "source": str(BASE_DIR / "samples" / "traffic1.mp4"),
            "lat": 28.6050,
            "lng": 77.2020,
            "road": "Southern Bypass",
        },
    ]

    # ─── Samples ─────────────────────────────────────────────────────────────
    SAMPLES_DIR = BASE_DIR / "samples"
