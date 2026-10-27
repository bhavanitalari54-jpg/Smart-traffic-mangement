"""
modules/alert_manager.py
──────────────────────────
Manages accident alert lifecycle:
  pending  →  confirmed  (human operator confirms)
  pending  →  dismissed  (human operator dismisses)

Stores alerts in Firebase (if configured) and keeps an in-memory cache
for fast dashboard access.  Emits real-time SocketIO events to all
connected dashboard clients.
"""

from __future__ import annotations

import base64
import logging
import time
import uuid
from typing import Dict, List, Optional

import cv2
import numpy as np

from modules.accident_detector import AccidentEvent

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Parameters
    ----------
    firebase : FirebaseManager | None
    socketio : SocketIO | None
        If provided, emits events on accident_alert / alert_update channels.
    """

    def __init__(self, firebase=None, socketio=None):
        self._firebase = firebase
        self._socketio = socketio
        # In-memory store: id → alert dict
        self._alerts: Dict[str, dict] = {}

    # ── Create ────────────────────────────────────────────────────────────

    def create_alert(self, event: AccidentEvent, camera_meta: dict) -> str:
        """
        Persist a new suspected-accident alert and notify clients.

        Returns the new alert ID.
        """
        alert_id = str(uuid.uuid4())[:8].upper()
        snapshot_b64 = self._encode_snapshot(event.snapshot)

        alert = {
            "id": alert_id,
            "camera_id": event.camera_id,
            "camera_name": camera_meta.get("name", event.camera_id),
            "road": camera_meta.get("road", "Unknown Road"),
            "lat": camera_meta.get("lat", 0.0),
            "lng": camera_meta.get("lng", 0.0),
            "confidence": event.confidence,
            "confidence_pct": event.confidence_pct,
            "trigger": event.trigger,
            "status": "pending",          # pending | confirmed | dismissed
            "timestamp": event.timestamp,
            "timestamp_str": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(event.timestamp)
            ),
            "snapshot": snapshot_b64,
            "acknowledged_by": None,
            "acknowledged_at": None,
        }

        self._alerts[alert_id] = alert

        # Persist to Firebase
        if self._firebase and self._firebase.enabled:
            try:
                self._firebase.save_alert(alert_id, alert)
            except Exception as exc:
                logger.warning("Firebase save failed: %s", exc)

        # Push to dashboard clients
        self._emit("accident_alert", {
            k: v for k, v in alert.items() if k != "snapshot"
        })

        logger.info(
            "🚨 Alert %s created – cam=%s trigger=%s conf=%d%%",
            alert_id, event.camera_id, event.trigger, event.confidence_pct,
        )
        return alert_id

    # ── Update Status ─────────────────────────────────────────────────────

    def update_status(
        self,
        alert_id: str,
        new_status: str,
        operator: str = "operator",
    ) -> bool:
        """Set status to 'confirmed' or 'dismissed'. Returns True on success."""
        if alert_id not in self._alerts:
            return False
        if new_status not in ("confirmed", "dismissed"):
            return False

        alert = self._alerts[alert_id]
        alert["status"] = new_status
        alert["acknowledged_by"] = operator
        alert["acknowledged_at"] = time.time()

        if self._firebase and self._firebase.enabled:
            try:
                self._firebase.update_alert(alert_id, {
                    "status": new_status,
                    "acknowledged_by": operator,
                    "acknowledged_at": alert["acknowledged_at"],
                })
            except Exception as exc:
                logger.warning("Firebase update failed: %s", exc)

        self._emit("alert_update", {
            "id": alert_id,
            "status": new_status,
            "acknowledged_by": operator,
        })

        logger.info("Alert %s → %s (by %s)", alert_id, new_status, operator)
        return True

    # ── Queries ───────────────────────────────────────────────────────────

    def get_all(self, status_filter: Optional[str] = None) -> List[dict]:
        alerts = list(self._alerts.values())
        if status_filter:
            alerts = [a for a in alerts if a["status"] == status_filter]
        return sorted(alerts, key=lambda a: a["timestamp"], reverse=True)

    def get_by_id(self, alert_id: str) -> Optional[dict]:
        return self._alerts.get(alert_id)

    def pending_count(self) -> int:
        return sum(1 for a in self._alerts.values() if a["status"] == "pending")

    def total_count(self) -> int:
        return len(self._alerts)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _emit(self, event: str, data: dict) -> None:
        if self._socketio:
            try:
                self._socketio.emit(event, data)
            except Exception as exc:
                logger.warning("SocketIO emit failed: %s", exc)

    @staticmethod
    def _encode_snapshot(frame: Optional[np.ndarray]) -> Optional[str]:
        if frame is None:
            return None
        try:
            # Resize to thumbnail
            thumb = cv2.resize(frame, (320, 240))
            _, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf.tobytes()).decode("utf-8")
        except Exception as exc:
            logger.warning("Snapshot encoding error: %s", exc)
            return None
