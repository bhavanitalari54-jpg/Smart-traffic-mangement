"""
database/firebase_manager.py
──────────────────────────────
Firebase Firestore wrapper.

If firebase_credentials.json is not present (or firebase-admin is not installed),
the manager runs in "mock mode" — all writes are silently dropped and reads
return empty results.  This lets the system run as a demo without Firebase.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FirebaseManager:
    """
    Thin wrapper around the Firebase Admin SDK (Firestore).

    Collections used:
      traffic_records   – per-frame traffic density readings
      accident_alerts   – accident event records
      cameras           – camera metadata
      signal_timings    – signal timing recommendations (latest per camera)
    """

    def __init__(self):
        self._db = None
        self.enabled = False
        self._init_firebase()

    # ── Initialisation ────────────────────────────────────────────────────

    def _init_firebase(self):
        from config import Config

        creds_path = Config.FIREBASE_CREDENTIALS_PATH
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                cred = credentials.Certificate(creds_path)
                firebase_admin.initialize_app(cred)

            self._db = firestore.client()
            self.enabled = True
            logger.info("Firebase Firestore connected.")
        except FileNotFoundError:
            logger.warning(
                "Firebase credentials not found at %s. "
                "Running in mock mode (no data persistence).",
                creds_path,
            )
        except ImportError:
            logger.warning("firebase-admin not installed. Running in mock mode.")
        except Exception as exc:
            logger.warning("Firebase init failed (%s). Running in mock mode.", exc)

    # ── Traffic Records ───────────────────────────────────────────────────

    def save_traffic_record(self, camera_id: str, record: dict) -> None:
        if not self.enabled:
            return
        try:
            self._db.collection("traffic_records").add({
                **record,
                "camera_id": camera_id,
                "saved_at": time.time(),
            })
        except Exception as exc:
            logger.error("save_traffic_record: %s", exc)

    def get_traffic_history(
        self, camera_id: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            docs = (
                self._db.collection("traffic_records")
                .where("camera_id", "==", camera_id)
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception as exc:
            logger.error("get_traffic_history: %s", exc)
            return []

    # ── Accident Alerts ───────────────────────────────────────────────────

    def save_alert(self, alert_id: str, alert: dict) -> None:
        if not self.enabled:
            return
        try:
            # Don't store large base64 snapshot in Firestore
            payload = {k: v for k, v in alert.items() if k != "snapshot"}
            self._db.collection("accident_alerts").document(alert_id).set(payload)
        except Exception as exc:
            logger.error("save_alert: %s", exc)

    def update_alert(self, alert_id: str, updates: dict) -> None:
        if not self.enabled:
            return
        try:
            self._db.collection("accident_alerts").document(alert_id).update(updates)
        except Exception as exc:
            logger.error("update_alert: %s", exc)

    def get_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.enabled:
            return []
        try:
            docs = (
                self._db.collection("accident_alerts")
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception as exc:
            logger.error("get_alerts: %s", exc)
            return []

    # ── Signal Timings ────────────────────────────────────────────────────

    def save_signal_timing(self, camera_id: str, timing: dict) -> None:
        if not self.enabled:
            return
        try:
            self._db.collection("signal_timings").document(camera_id).set({
                **timing,
                "camera_id": camera_id,
                "updated_at": time.time(),
            })
        except Exception as exc:
            logger.error("save_signal_timing: %s", exc)

    # ── Camera Metadata ───────────────────────────────────────────────────

    def upsert_camera(self, camera: dict) -> None:
        if not self.enabled:
            return
        try:
            self._db.collection("cameras").document(camera["id"]).set(camera)
        except Exception as exc:
            logger.error("upsert_camera: %s", exc)
