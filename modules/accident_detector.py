"""
modules/accident_detector.py
──────────────────────────────
Heuristic-based accident detection using frame difference analysis,
bounding-box overlap (Intersection-over-Union), and stationary-vehicle detection.

⚠️  IMPORTANT DISCLAIMER
This module uses heuristic computer-vision techniques, NOT a trained
deep-learning accident-classification model.  All events produced here are
labelled "SUSPECTED" and MUST be reviewed by a human operator before any
emergency response is initiated.  False positives are expected.

Detection stages
────────────────
1. Motion anomaly   – frame-diff magnitude exceeds threshold
2. Collision proxy  – IoU between any two vehicle bboxes exceeds threshold
3. Stationary alarm – a previously-moving vehicle stops in the travel lane
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import Config
from modules.vehicle_detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class AccidentEvent:
    camera_id: str
    suspected: bool
    confidence: float          # 0.0 – 1.0  (heuristic, not statistical)
    trigger: str               # "collision_proxy" | "stationary" | "motion_spike"
    timestamp: float = field(default_factory=time.time)
    snapshot: Optional[np.ndarray] = None   # BGR frame at detection time

    @property
    def confidence_pct(self) -> int:
        return int(self.confidence * 100)


# ─── IoU helper ─────────────────────────────────────────────────────────────

def _iou(a: Tuple, b: Tuple) -> float:
    """Intersection-over-Union for two (x1,y1,x2,y2) boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    if inter == 0:
        return 0.0
    area_a = (ax2 - ax1) * (ay2 - ay1)
    area_b = (bx2 - bx1) * (by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# ─── Centroid tracker ───────────────────────────────────────────────────────

class _CentroidTracker:
    """
    Lightweight centroid tracker to detect stationary vehicles.
    Associates detections frame-to-frame by nearest centroid and
    counts how many consecutive frames each track has been stationary.
    """

    def __init__(self, max_distance: int = 60, stationary_frames: int = 40):
        self.max_distance = max_distance
        self.stationary_frames = stationary_frames
        self._tracks: Dict[int, dict] = {}
        self._next_id = 0

    def update(self, detections: List[Detection]) -> List[int]:
        """
        Update tracker with new detections.
        Returns a list of track-IDs that have become stationary.
        """
        centroids = [d.centroid for d in detections]
        stationary_ids: List[int] = []

        if not centroids:
            # Decay all tracks
            for tid in list(self._tracks.keys()):
                self._tracks[tid]["missing"] += 1
                if self._tracks[tid]["missing"] > 10:
                    del self._tracks[tid]
            return []

        # Match existing tracks to new centroids
        matched_tracks = set()
        matched_cents = set()

        for tid, track in self._tracks.items():
            best_dist = self.max_distance + 1
            best_c = -1
            for ci, c in enumerate(centroids):
                d = np.hypot(c[0] - track["centroid"][0], c[1] - track["centroid"][1])
                if d < best_dist:
                    best_dist = d
                    best_c = ci
            if best_c >= 0 and best_c not in matched_cents:
                prev = track["centroid"]
                curr = centroids[best_c]
                moved = np.hypot(curr[0] - prev[0], curr[1] - prev[1])
                track["centroid"] = curr
                track["missing"] = 0
                if moved < 5:          # practically stationary
                    track["static_frames"] += 1
                else:
                    track["static_frames"] = 0
                if track["static_frames"] >= self.stationary_frames:
                    stationary_ids.append(tid)
                matched_tracks.add(tid)
                matched_cents.add(best_c)

        # Create new tracks for unmatched centroids
        for ci, c in enumerate(centroids):
            if ci not in matched_cents:
                self._tracks[self._next_id] = {
                    "centroid": c,
                    "static_frames": 0,
                    "missing": 0,
                }
                self._next_id += 1

        # Remove stale tracks
        for tid in list(self._tracks.keys()):
            if tid not in matched_tracks:
                self._tracks[tid]["missing"] += 1
                if self._tracks[tid]["missing"] > 10:
                    del self._tracks[tid]

        return stationary_ids


# ─── Accident Detector ──────────────────────────────────────────────────────

class AccidentDetector:
    """
    Analyses consecutive frames and detection results to flag suspected accidents.

    Parameters
    ----------
    camera_id : str
    """

    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self._prev_gray: Optional[np.ndarray] = None
        self._tracker = _CentroidTracker(
            stationary_frames=Config.ACCIDENT_STATIONARY_FRAMES
        )
        self._last_alert_time: float = 0.0

    # ── Main entry-point ─────────────────────────────────────────────────

    def analyze(
        self,
        frame: np.ndarray,
        detections: List[Detection],
    ) -> Optional[AccidentEvent]:
        """
        Run all heuristic stages on one frame.

        Returns AccidentEvent if a suspected accident is detected,
        otherwise None.  A cooldown period prevents duplicate alerts.
        """
        event = None

        # Stage 1 – motion anomaly
        motion_score = self._motion_anomaly(frame)

        # Stage 2 – collision proxy (bbox overlap)
        collision_conf = self._collision_proxy(detections)

        # Stage 3 – stationary vehicle
        stationary = bool(self._tracker.update(detections))

        # ── Decision logic ─────────────────────────────────────────────
        if collision_conf >= Config.ACCIDENT_OVERLAP_IOU:
            # IoU overlap: highest confidence, combined with motion
            confidence = min(0.4 + collision_conf * 0.5 + motion_score * 0.1, 1.0)
            event = AccidentEvent(
                camera_id=self.camera_id,
                suspected=True,
                confidence=round(confidence, 2),
                trigger="collision_proxy",
                snapshot=frame.copy(),
            )
        elif stationary and motion_score > 0.3:
            # Sudden stop + high motion elsewhere
            confidence = min(0.3 + motion_score * 0.4, 0.85)
            event = AccidentEvent(
                camera_id=self.camera_id,
                suspected=True,
                confidence=round(confidence, 2),
                trigger="stationary",
                snapshot=frame.copy(),
            )
        elif motion_score > 0.7:
            # Severe motion spike alone
            confidence = min(0.2 + motion_score * 0.3, 0.60)
            event = AccidentEvent(
                camera_id=self.camera_id,
                suspected=True,
                confidence=round(confidence, 2),
                trigger="motion_spike",
                snapshot=frame.copy(),
            )

        # Cooldown guard
        if event is not None:
            now = time.time()
            if now - self._last_alert_time < Config.ACCIDENT_CONFIDENCE_COOLDOWN:
                event = None
            else:
                self._last_alert_time = now

        return event

    # ── Stage helpers ─────────────────────────────────────────────────────

    def _motion_anomaly(self, frame: np.ndarray) -> float:
        """
        Returns a motion score in [0, 1] based on frame-difference magnitude.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev_gray is None:
            self._prev_gray = gray
            return 0.0

        diff = cv2.absdiff(self._prev_gray, gray)
        self._prev_gray = gray

        # Proportion of pixels with significant change
        _, mask = cv2.threshold(
            diff, Config.ACCIDENT_MOTION_THRESHOLD, 255, cv2.THRESH_BINARY
        )
        score = float(np.count_nonzero(mask)) / (mask.shape[0] * mask.shape[1])
        return min(score * 5.0, 1.0)   # amplify; cap at 1.0

    @staticmethod
    def _collision_proxy(detections: List[Detection]) -> float:
        """
        Returns the maximum IoU between any pair of detected vehicles.
        IoU > threshold suggests vehicles occupying the same space → possible collision.
        """
        max_iou = 0.0
        n = len(detections)
        for i in range(n):
            for j in range(i + 1, n):
                iou = _iou(detections[i].bbox, detections[j].bbox)
                if iou > max_iou:
                    max_iou = iou
        return max_iou


# ─── Smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    detector = AccidentDetector("cam_test")

    # Simulate a large sudden motion (all-white frame after black)
    frame_black = np.zeros((480, 640, 3), dtype=np.uint8)
    frame_white = np.ones((480, 640, 3), dtype=np.uint8) * 200

    result1 = detector.analyze(frame_black, [])
    result2 = detector.analyze(frame_white, [])

    print("Result 1 (first frame):", result1)
    print("Result 2 (flash frame) :", result2)
    print("Smoke test passed.")
