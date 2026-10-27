"""
modules/video_processor.py
───────────────────────────
VideoProcessor: runs per camera in a background daemon thread.

  - Opens a cv2.VideoCapture (file, RTSP, or webcam)
  - Processes every N frames through the detection pipeline
  - Maintains a shared "latest annotated frame" buffer for MJPEG streaming
  - Pushes stats updates via SocketIO
  - Triggers alert creation on accident events
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

from config import Config
from modules.vehicle_detector import VehicleDetector
from modules.traffic_analyzer import TrafficAnalyzer
from modules.accident_detector import AccidentDetector

logger = logging.getLogger(__name__)

# Shared resources (injected at startup)
_vehicle_detector: Optional[VehicleDetector] = None
_traffic_analyzer: Optional[TrafficAnalyzer] = None


def init_shared_resources(detector: VehicleDetector, analyzer: TrafficAnalyzer):
    """Call once at app startup to inject shared model instances."""
    global _vehicle_detector, _traffic_analyzer
    _vehicle_detector = detector
    _traffic_analyzer = analyzer


class VideoProcessor:
    """
    Manages video capture and frame processing for one camera.

    Parameters
    ----------
    camera      : dict with keys id, name, source, lat, lng, road
    alert_manager : AlertManager instance
    socketio    : Flask-SocketIO instance (or None)
    """

    def __init__(self, camera: dict, alert_manager=None, socketio=None):
        self.camera = camera
        self.camera_id: str = camera["id"]
        self._alert_mgr = alert_manager
        self._socketio = socketio

        # Per-camera accident detector (stateful)
        self._accident_detector = AccidentDetector(self.camera_id)

        # Frame buffer – latest annotated frame for MJPEG streaming
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._placeholder: np.ndarray = self._make_placeholder()

        # Stats
        self._stats: dict = {
            "camera_id": self.camera_id,
            "total": 0,
            "counts": {},
            "density": "LOW",
            "signal": Config.SIGNAL_TIMINGS["LOW"],
            "timestamp": time.time(),
        }
        self._stats_lock = threading.Lock()

        # Thread control
        self._running = False
        self._thread: Optional[threading.Thread] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name=f"vp-{self.camera_id}"
        )
        self._thread.start()
        logger.info("VideoProcessor started: %s", self.camera_id)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        logger.info("VideoProcessor stopped: %s", self.camera_id)

    # ── MJPEG Frame Generator ─────────────────────────────────────────────

    def generate_frames(self):
        """
        Generator that yields MJPEG-encoded frames for the /video_feed route.
        """
        target_delay = 1.0 / Config.STREAM_FPS
        while True:
            start = time.time()
            frame = self._get_current_frame()
            _, buf = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
            )
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + buf.tobytes()
                + b"\r\n"
            )
            elapsed = time.time() - start
            sleep_for = target_delay - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)

    # ── Stats ─────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        with self._stats_lock:
            return dict(self._stats)

    # ── Internal Processing Loop ──────────────────────────────────────────

    def _run(self):
        source = self.camera.get("source", 0)
        cap = None
        frame_idx = 0

        while self._running:
            # (Re-)open capture
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    logger.warning(
                        "Cannot open video source for %s: %s", self.camera_id, source
                    )
                    time.sleep(3)
                    continue
                logger.info("Opened source for %s: %s", self.camera_id, source)

            ret, frame = cap.read()
            if not ret:
                # End of file → loop
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_idx = 0
                continue

            frame_idx += 1

            # Resize for consistent processing
            frame = cv2.resize(frame, (Config.FRAME_WIDTH, Config.FRAME_HEIGHT))

            # Only run heavy detection every N frames
            if frame_idx % Config.PROCESS_EVERY_N_FRAMES == 0:
                processed = self._process_frame(frame)
            else:
                # Use last annotated frame with live overlay
                processed = self._overlay_minimal(frame)

            with self._frame_lock:
                self._latest_frame = processed

        if cap:
            cap.release()

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """Full pipeline: detect → analyze → check accident → update stats."""
        annotated = frame.copy()

        # Vehicle detection
        if _vehicle_detector and _vehicle_detector.ready:
            det_result = _vehicle_detector.detect(frame, annotate=True)
            annotated = det_result.annotated_frame
            detections = det_result.detections
            counts = det_result.counts
            total = det_result.total
        else:
            detections = []
            counts = {}
            total = 0

        # Traffic analysis
        if _traffic_analyzer:
            density_result = _traffic_analyzer.analyze(
                self.camera_id, total, counts
            )
            density_label = density_result.density_label
            signal = density_result.signal_timing
        else:
            density_label = "LOW"
            signal = Config.SIGNAL_TIMINGS["LOW"]

        # Accident detection
        accident_event = self._accident_detector.analyze(frame, detections)
        if accident_event and self._alert_mgr:
            self._alert_mgr.create_alert(accident_event, self.camera)

        # Update stats
        stats = {
            "camera_id": self.camera_id,
            "camera_name": self.camera.get("name", self.camera_id),
            "total": total,
            "counts": counts,
            "density": density_label,
            "signal": signal,
            "accident": accident_event is not None,
            "timestamp": time.time(),
        }
        with self._stats_lock:
            self._stats = stats

        # Push stats via SocketIO
        self._emit_stats(stats)

        # Draw HUD overlay
        annotated = self._draw_hud(annotated, density_label, total, signal)
        return annotated

    def _overlay_minimal(self, frame: np.ndarray) -> np.ndarray:
        """Lightweight overlay for non-processed frames."""
        with self._stats_lock:
            density = self._stats.get("density", "LOW")
            total = self._stats.get("total", 0)
            signal = self._stats.get("signal", Config.SIGNAL_TIMINGS["LOW"])
        return self._draw_hud(frame.copy(), density, total, signal)

    @staticmethod
    def _draw_hud(
        frame: np.ndarray,
        density: str,
        total: int,
        signal: dict,
    ) -> np.ndarray:
        """Draw a semi-transparent HUD strip at the bottom of the frame."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - 60), (w, h), (10, 14, 26), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        density_col = {"LOW": (0, 200, 80), "MEDIUM": (0, 200, 255), "HIGH": (0, 80, 255)}.get(
            density, (200, 200, 200)
        )
        cv2.putText(
            frame,
            f"Vehicles: {total}  |  Density: {density}  |  "
            f"G:{signal['green']}s  Y:{signal['yellow']}s  R:{signal['red']}s",
            (8, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.55, density_col, 1, cv2.LINE_AA,
        )
        # Timestamp
        ts = time.strftime("%H:%M:%S")
        cv2.putText(
            frame, ts, (w - 80, h - 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA,
        )
        return frame

    def _get_current_frame(self) -> np.ndarray:
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return self._placeholder.copy()

    def _emit_stats(self, stats: dict) -> None:
        if self._socketio:
            try:
                payload = {k: v for k, v in stats.items() if k != "counts"}
                payload["counts"] = stats.get("counts", {})
                self._socketio.emit("stats_update", payload)
            except Exception as exc:
                logger.debug("SocketIO emit error: %s", exc)

    @staticmethod
    def _make_placeholder() -> np.ndarray:
        """Placeholder frame shown while the capture is initialising."""
        f = np.zeros((Config.FRAME_HEIGHT, Config.FRAME_WIDTH, 3), dtype=np.uint8)
        f[:] = (10, 14, 26)
        cv2.putText(
            f, "Connecting to camera...",
            (80, Config.FRAME_HEIGHT // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 212, 255), 2, cv2.LINE_AA,
        )
        return f
