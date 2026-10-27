"""
modules/vehicle_detector.py
────────────────────────────
YOLOv8-based vehicle detection module.
Filters COCO classes: car (2), motorcycle (3), bus (5), truck (7).
Returns per-frame detection results including bounding boxes,
class labels, confidence scores, and per-class counts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    """Single vehicle detection result."""
    bbox: tuple          # (x1, y1, x2, y2) in pixel coords
    class_id: int
    class_name: str
    confidence: float
    centroid: tuple = field(init=False)

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.centroid = ((x1 + x2) // 2, (y1 + y2) // 2)


@dataclass
class DetectionResult:
    """Aggregated result for one processed frame."""
    detections: List[Detection]
    counts: Dict[str, int]
    total: int
    annotated_frame: Optional[np.ndarray] = None


# ─── Colour palette per vehicle type ────────────────────────────────────────
_COLOURS = {
    "car":        (0, 212, 255),    # cyan
    "motorcycle": (123, 47, 247),   # purple
    "bus":        (0, 255, 128),    # green
    "truck":      (255, 165, 0),    # orange
}
_DEFAULT_COLOUR = (200, 200, 200)


class VehicleDetector:
    """
    Wraps an Ultralytics YOLOv8 model for real-time vehicle detection.

    Parameters
    ----------
    model_path : str
        Path to a YOLO .pt weights file, or model name (e.g. 'yolov8n.pt')
        which will be auto-downloaded on first use.
    confidence : float
        Minimum confidence score to accept a detection (0–1).
    vehicle_classes : dict
        Mapping of COCO class-id → label string.
    """

    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence: float = 0.50,
        vehicle_classes: Optional[Dict[int, str]] = None,
    ):
        self.model_path = model_path
        self.confidence = confidence
        self.vehicle_classes = vehicle_classes or {
            2: "car",
            3: "motorcycle",
            5: "bus",
            7: "truck",
        }
        self._model = None
        self._load_model()

    # ── Model Loading ────────────────────────────────────────────────────────

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            self._model = YOLO(self.model_path)
            logger.info("YOLOv8 model loaded: %s", self.model_path)
        except ImportError:
            logger.error(
                "ultralytics not installed. Run: pip install ultralytics"
            )
            self._model = None
        except Exception as exc:
            logger.error("Failed to load YOLO model: %s", exc)
            self._model = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    # ── Detection ────────────────────────────────────────────────────────────

    def detect(self, frame: np.ndarray, annotate: bool = True) -> DetectionResult:
        """
        Run inference on a single BGR frame.

        Parameters
        ----------
        frame      : BGR image (H×W×3 numpy array)
        annotate   : If True, draw bounding boxes on a copy of the frame.

        Returns
        -------
        DetectionResult
        """
        if self._model is None:
            return self._mock_detect(frame, annotate)

        try:
            results = self._model.predict(
                frame,
                conf=self.confidence,
                classes=list(self.vehicle_classes.keys()),
                verbose=False,
            )
        except Exception as exc:
            logger.warning("YOLO inference error: %s", exc)
            return self._mock_detect(frame, annotate)

        detections: List[Detection] = []
        counts: Dict[str, int] = {v: 0 for v in self.vehicle_classes.values()}

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cid = int(box.cls[0])
                if cid not in self.vehicle_classes:
                    continue
                label = self.vehicle_classes[cid]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                det = Detection(
                    bbox=(x1, y1, x2, y2),
                    class_id=cid,
                    class_name=label,
                    confidence=conf,
                )
                detections.append(det)
                counts[label] = counts.get(label, 0) + 1

        annotated = self._annotate(frame.copy(), detections) if annotate else frame

        return DetectionResult(
            detections=detections,
            counts=counts,
            total=len(detections),
            annotated_frame=annotated,
        )

    # ── Annotation ───────────────────────────────────────────────────────────

    def _annotate(self, frame: np.ndarray, detections: List[Detection]) -> np.ndarray:
        """Draw bounding boxes and labels on *frame* (in-place)."""
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            colour = _COLOURS.get(det.class_name, _DEFAULT_COLOUR)
            # Bounding box
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
            # Label background
            label = f"{det.class_name} {det.confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - 6), (x1 + tw + 4, y1), colour, -1)
            # Label text
            cv2.putText(
                frame, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA
            )
        # Vehicle count overlay
        y_off = 30
        for vtype, cnt in _count_from_detections(detections).items():
            text = f"{vtype.capitalize()}: {cnt}"
            cv2.putText(
                frame, text, (10, y_off),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                _COLOURS.get(vtype, _DEFAULT_COLOUR), 2, cv2.LINE_AA,
            )
            y_off += 24
        return frame

    # ── Mock / Fallback ──────────────────────────────────────────────────────

    def _mock_detect(self, frame: np.ndarray, annotate: bool) -> DetectionResult:
        """
        Fallback used when YOLO is unavailable.
        Returns zero counts and the original frame.
        """
        counts = {v: 0 for v in self.vehicle_classes.values()}
        return DetectionResult(
            detections=[],
            counts=counts,
            total=0,
            annotated_frame=frame.copy() if annotate else frame,
        )


def _count_from_detections(detections: List[Detection]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for d in detections:
        counts[d.class_name] = counts.get(d.class_name, 0) + 1
    return counts


# ─── Smoke-test ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys

    detector = VehicleDetector()
    if not detector.ready:
        print("YOLO model not available – running mock test.")
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = detector.detect(frame)
        print("Mock result – total vehicles:", result.total)
        sys.exit(0)

    # Test on a blank frame (no vehicles expected)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(frame)
    print("Detected vehicles:", result.total)
    print("Counts:", result.counts)
    cv2.imshow("Annotated", result.annotated_frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
