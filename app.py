"""
app.py – Flask application entry point
Smart Traffic Management & Accident Detection System

Endpoints
─────────
Pages         GET  /login  /dashboard  /monitoring  /accidents
              GET  /signals  /map  /history  /settings

REST API      GET  /api/stats
              GET  /api/alerts
              GET  /api/alerts/<id>
              POST /api/alerts/<id>/confirm
              POST /api/alerts/<id>/dismiss
              GET  /api/cameras
              GET  /api/signal-timings
              GET  /api/history
              POST /api/login   POST /api/logout

Video         GET  /video_feed/<camera_id>

SocketIO events (server → client)
  stats_update     – per-camera vehicle & density data
  accident_alert   – new suspected accident
  alert_update     – status change (confirmed / dismissed)
"""

import logging
import time
from functools import wraps

from flask import (
    Flask, Response, jsonify, redirect, render_template,
    request, session, url_for,
)
from flask_socketio import SocketIO

from config import Config
from database.firebase_manager import FirebaseManager
from modules.alert_manager import AlertManager
from modules.traffic_analyzer import TrafficAnalyzer
from modules.vehicle_detector import VehicleDetector
from modules.video_processor import VideoProcessor, init_shared_resources

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ─── App & SocketIO ───────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# ─── Services ─────────────────────────────────────────────────────────────────
firebase = FirebaseManager()
alert_manager = AlertManager(firebase=firebase, socketio=socketio)
traffic_analyzer = TrafficAnalyzer()
vehicle_detector = VehicleDetector(
    model_path=Config.YOLO_MODEL,
    confidence=Config.YOLO_CONFIDENCE,
    vehicle_classes=Config.VEHICLE_CLASS_IDS,
)
init_shared_resources(vehicle_detector, traffic_analyzer)

# ─── Video Processors (one per camera) ───────────────────────────────────────
processors: dict[str, VideoProcessor] = {}

for _cam in Config.CAMERAS:
    vp = VideoProcessor(_cam, alert_manager=alert_manager, socketio=socketio)
    processors[_cam["id"]] = vp
    vp.start()
    logger.info("Started processor for camera: %s", _cam["id"])

# ─── Auth helper ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))


@app.route("/login")
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    cameras = Config.CAMERAS
    stats = {cam_id: vp.get_stats() for cam_id, vp in processors.items()}
    alerts = alert_manager.get_all()[:5]
    return render_template(
        "dashboard.html",
        cameras=cameras,
        stats=stats,
        alerts=alerts,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/monitoring")
@login_required
def monitoring():
    cameras = Config.CAMERAS
    active_cam = request.args.get("cam", cameras[0]["id"] if cameras else "")
    stats = {cam_id: vp.get_stats() for cam_id, vp in processors.items()}
    return render_template(
        "monitoring.html",
        cameras=cameras,
        active_cam=active_cam,
        stats=stats,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/accidents")
@login_required
def accidents():
    alerts = alert_manager.get_all()
    return render_template(
        "accidents.html",
        alerts=alerts,
        cameras=Config.CAMERAS,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/signals")
@login_required
def signals():
    stats = {cam_id: vp.get_stats() for cam_id, vp in processors.items()}
    cameras = Config.CAMERAS
    return render_template(
        "signals.html",
        cameras=cameras,
        stats=stats,
        signal_timings=Config.SIGNAL_TIMINGS,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/map")
@login_required
def map_page():
    alerts = alert_manager.get_all()
    cameras = Config.CAMERAS
    return render_template(
        "map.html",
        cameras=cameras,
        alerts=alerts,
        maps_key=Config.GOOGLE_MAPS_API_KEY,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/history")
@login_required
def history():
    alerts = alert_manager.get_all()
    return render_template(
        "history.html",
        alerts=alerts,
        cameras=Config.CAMERAS,
        pending_count=alert_manager.pending_count(),
    )


@app.route("/settings")
@login_required
def settings():
    return render_template(
        "settings.html",
        cameras=Config.CAMERAS,
        config=Config,
        pending_count=alert_manager.pending_count(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  AUTH API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if username == Config.DEMO_USERNAME and password == Config.DEMO_PASSWORD:
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"success": True, "redirect": url_for("dashboard")})
    return jsonify({"success": False, "error": "Invalid credentials"}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True, "redirect": url_for("login_page")})


# ═══════════════════════════════════════════════════════════════════════════════
#  VIDEO STREAM
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/video_feed/<camera_id>")
@login_required
def video_feed(camera_id: str):
    if camera_id not in processors:
        return "Camera not found", 404
    return Response(
        processors[camera_id].generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/stats")
@login_required
def api_stats():
    stats = {}
    total_vehicles = 0
    for cam_id, vp in processors.items():
        s = vp.get_stats()
        stats[cam_id] = s
        total_vehicles += s.get("total", 0)
    return jsonify({
        "total_vehicles": total_vehicles,
        "cameras": stats,
        "alert_count": alert_manager.total_count(),
        "pending_alerts": alert_manager.pending_count(),
        "active_cameras": len(processors),
        "timestamp": time.time(),
    })


@app.route("/api/alerts")
@login_required
def api_alerts():
    status = request.args.get("status")
    alerts = alert_manager.get_all(status_filter=status)
    # Strip large snapshot fields for list view
    return jsonify([
        {k: v for k, v in a.items() if k != "snapshot"}
        for a in alerts
    ])


@app.route("/api/alerts/<alert_id>")
@login_required
def api_alert_detail(alert_id: str):
    alert = alert_manager.get_by_id(alert_id)
    if not alert:
        return jsonify({"error": "Not found"}), 404
    return jsonify(alert)


@app.route("/api/alerts/<alert_id>/confirm", methods=["POST"])
@login_required
def api_confirm_alert(alert_id: str):
    operator = session.get("username", "operator")
    ok = alert_manager.update_status(alert_id, "confirmed", operator)
    if not ok:
        return jsonify({"error": "Not found or invalid"}), 404
    return jsonify({"success": True, "id": alert_id, "status": "confirmed"})


@app.route("/api/alerts/<alert_id>/dismiss", methods=["POST"])
@login_required
def api_dismiss_alert(alert_id: str):
    operator = session.get("username", "operator")
    ok = alert_manager.update_status(alert_id, "dismissed", operator)
    if not ok:
        return jsonify({"error": "Not found or invalid"}), 404
    return jsonify({"success": True, "id": alert_id, "status": "dismissed"})


@app.route("/api/cameras")
@login_required
def api_cameras():
    result = []
    for cam in Config.CAMERAS:
        stats = processors[cam["id"]].get_stats() if cam["id"] in processors else {}
        result.append({**cam, "stats": stats})
    return jsonify(result)


@app.route("/api/signal-timings")
@login_required
def api_signal_timings():
    timings = {}
    for cam in Config.CAMERAS:
        s = processors[cam["id"]].get_stats() if cam["id"] in processors else {}
        density = s.get("density", "LOW")
        timings[cam["id"]] = {
            "camera_name": cam["name"],
            "road": cam["road"],
            "density": density,
            "timing": s.get("signal", Config.SIGNAL_TIMINGS[density]),
        }
    return jsonify(timings)


@app.route("/api/history")
@login_required
def api_history():
    alerts = alert_manager.get_all()
    return jsonify([{k: v for k, v in a.items() if k != "snapshot"} for a in alerts])


# ═══════════════════════════════════════════════════════════════════════════════
#  SOCKETIO EVENTS
# ═══════════════════════════════════════════════════════════════════════════════

@socketio.on("connect")
def handle_connect():
    logger.debug("Client connected: %s", request.sid)


@socketio.on("disconnect")
def handle_disconnect():
    logger.debug("Client disconnected: %s", request.sid)


@socketio.on("subscribe_camera")
def handle_subscribe(data):
    cam_id = data.get("camera_id")
    logger.debug("Client %s subscribed to camera %s", request.sid, cam_id)


# ═══════════════════════════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", error="Page not found (404)"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("base.html", error=f"Internal server error: {e}"), 500


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  Smart Traffic Management System")
    logger.info("  http://localhost:5000")
    logger.info("  Login: %s / %s", Config.DEMO_USERNAME, Config.DEMO_PASSWORD)
    logger.info("  Firebase: %s", "enabled" if firebase.enabled else "mock mode")
    logger.info("  YOLO: %s", "ready" if vehicle_detector.ready else "unavailable")
    logger.info("=" * 60)
    socketio.run(app, host="0.0.0.0", port=5000, debug=Config.DEBUG, use_reloader=False, allow_unsafe_werkzeug=True)
