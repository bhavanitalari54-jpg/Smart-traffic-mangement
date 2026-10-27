/**
 * map.js – Google Maps integration for traffic dashboard.
 *
 * Camera markers : blue  (🔵) showing live density
 * Accident markers: red  (🔴) for pending/confirmed alerts
 *
 * USAGE: window.CAMERA_DATA and window.ALERT_DATA must be set
 * by the template before this script loads.
 */

let map = null;
const cameraMarkers = {};  // camera_id → google.maps.Marker
const alertMarkers  = {};  // alert_id  → google.maps.Marker
const infoWindows   = {};

// ── Initialise map ───────────────────────────────────────────────────────────

window.initMap = function () {
  const cameras = window.CAMERA_DATA || [];
  const alerts  = window.ALERT_DATA  || [];

  // Centre on first camera or default (New Delhi)
  const centre = cameras.length
    ? { lat: cameras[0].lat, lng: cameras[0].lng }
    : { lat: 28.6139, lng: 77.2090 };

  map = new google.maps.Map(document.getElementById('map-container'), {
    center: centre,
    zoom: 14,
    mapTypeId: 'roadmap',
    styles: DARK_MAP_STYLE,
    disableDefaultUI: false,
    zoomControl: true,
    streetViewControl: false,
    mapTypeControl: false,
    fullscreenControl: true,
  });

  cameras.forEach(addCameraMarker);
  alerts.forEach(addAlertMarker);

  // Real-time updates
  if (typeof socket !== 'undefined') {
    socket.on('stats_update', updateCameraMarker);
    socket.on('accident_alert', addAlertMarkerFromSocket);
  }
};

// ── Camera Markers ───────────────────────────────────────────────────────────

function addCameraMarker(cam) {
  const marker = new google.maps.Marker({
    position: { lat: cam.lat, lng: cam.lng },
    map,
    title: cam.name,
    icon: cameraIcon('LOW'),
    animation: google.maps.Animation.DROP,
  });

  const iw = new google.maps.InfoWindow({
    content: buildCameraInfoWindow(cam, cam.stats || {}),
  });

  marker.addListener('click', () => {
    closeAllInfoWindows();
    iw.open(map, marker);
  });

  cameraMarkers[cam.id] = marker;
  infoWindows[cam.id] = iw;
}

function updateCameraMarker(data) {
  const marker = cameraMarkers[data.camera_id];
  if (!marker) return;
  marker.setIcon(cameraIcon(data.density || 'LOW'));

  const iw = infoWindows[data.camera_id];
  if (iw && iw.getMap()) {
    iw.setContent(buildCameraInfoWindow({ id: data.camera_id, name: data.camera_name }, data));
  }
}

function buildCameraInfoWindow(cam, stats) {
  const density = stats.density || 'LOW';
  const total   = stats.total   || 0;
  const col = { LOW: '#00c853', MEDIUM: '#ffd600', HIGH: '#f44336' }[density] || '#aaa';
  return `
    <div style="font-family:Inter,sans-serif;min-width:200px;color:#333;">
      <h3 style="margin:0 0 8px;font-size:14px;color:#111;">📷 ${escHtml(cam.name || cam.id)}</h3>
      <p style="margin:4px 0;font-size:12px;">🚗 Vehicles: <strong>${total}</strong></p>
      <p style="margin:4px 0;font-size:12px;">
        Density: <strong style="color:${col}">${density}</strong>
      </p>
      ${stats.signal ? `
      <p style="margin:4px 0;font-size:12px;">
        🟢 ${stats.signal.green}s &nbsp; 🟡 ${stats.signal.yellow}s &nbsp; 🔴 ${stats.signal.red}s
      </p>` : ''}
    </div>`;
}

function cameraIcon(density) {
  const fill = { LOW: '#00c853', MEDIUM: '#ffd600', HIGH: '#f44336' }[density] || '#00d4ff';
  return {
    path: google.maps.SymbolPath.CIRCLE,
    fillColor: fill,
    fillOpacity: 0.9,
    strokeColor: '#fff',
    strokeWeight: 2,
    scale: 10,
  };
}

// ── Accident Markers ─────────────────────────────────────────────────────────

function addAlertMarker(alert) {
  if (!alert.lat || !alert.lng) return;
  const marker = new google.maps.Marker({
    position: { lat: alert.lat, lng: alert.lng },
    map,
    title: `Alert #${alert.id}`,
    icon: accidentIcon(alert.status),
    animation: google.maps.Animation.BOUNCE,
  });

  setTimeout(() => marker.setAnimation(null), 2000);

  const iw = new google.maps.InfoWindow({
    content: buildAlertInfoWindow(alert),
  });

  marker.addListener('click', () => {
    closeAllInfoWindows();
    iw.open(map, marker);
  });

  alertMarkers[alert.id] = marker;
  infoWindows[`alert_${alert.id}`] = iw;
}

function addAlertMarkerFromSocket(alert) {
  // Use first camera's coords if none supplied
  const cam = (window.CAMERA_DATA || []).find(c => c.id === alert.camera_id);
  if (cam && !alert.lat) {
    alert.lat = cam.lat;
    alert.lng = cam.lng;
  }
  addAlertMarker(alert);
}

function buildAlertInfoWindow(alert) {
  const col = alert.status === 'confirmed' ? '#f44336' : '#ffd600';
  return `
    <div style="font-family:Inter,sans-serif;min-width:220px;color:#333;">
      <h3 style="margin:0 0 8px;font-size:14px;color:#c62828;">🚨 Suspected Accident</h3>
      <p style="margin:3px 0;font-size:12px;">ID: <code>#${escHtml(alert.id)}</code></p>
      <p style="margin:3px 0;font-size:12px;">Camera: <strong>${escHtml(alert.camera_name || alert.camera_id)}</strong></p>
      <p style="margin:3px 0;font-size:12px;">Time: ${escHtml(alert.timestamp_str || '')}</p>
      <p style="margin:3px 0;font-size:12px;">
        Status: <strong style="color:${col}">${escHtml(alert.status)}</strong>
        &nbsp; Conf: ${alert.confidence_pct || 0}%
      </p>
      <p style="margin:8px 0 0;font-size:11px;color:#777;">
        ⚠️ Human confirmation required.
      </p>
    </div>`;
}

function accidentIcon(status) {
  const fill = status === 'confirmed' ? '#f44336' : '#ffd600';
  return {
    path: google.maps.SymbolPath.FORWARD_CLOSED_ARROW,
    fillColor: fill,
    fillOpacity: 0.95,
    strokeColor: '#fff',
    strokeWeight: 1.5,
    scale: 6,
    rotation: 0,
  };
}

// ── Info window helpers ──────────────────────────────────────────────────────

function closeAllInfoWindows() {
  for (const iw of Object.values(infoWindows)) {
    iw.close();
  }
}

// ── Stub for no-key mode ─────────────────────────────────────────────────────
// If the Google Maps key is not configured, show a placeholder map.

document.addEventListener('DOMContentLoaded', () => {
  const key = window.MAPS_KEY || '';
  if (!key || key === 'YOUR_GOOGLE_MAPS_API_KEY') {
    const container = document.getElementById('map-container');
    if (container) {
      container.innerHTML = `
        <div style="
          display:flex;flex-direction:column;align-items:center;justify-content:center;
          height:100%;color:#7986cb;gap:16px;background:#0a0e1a;
        ">
          <div style="font-size:3rem;">🗺️</div>
          <div style="font-size:1rem;font-weight:600;">Google Maps not configured</div>
          <div style="font-size:0.82rem;color:#455a7a;text-align:center;max-width:340px;">
            Set your <code style="color:#00d4ff;">GOOGLE_MAPS_KEY</code> environment variable
            or update <code style="color:#00d4ff;">GOOGLE_MAPS_API_KEY</code> in
            <code style="color:#00d4ff;">config.py</code> to enable the interactive map.
          </div>
          <div style="margin-top:12px;font-size:0.78rem;color:#455a7a;">
            ${(window.CAMERA_DATA || []).map(c =>
              `📷 ${escHtml(c.name)}: (${c.lat}, ${c.lng})`
            ).join('<br>')}
          </div>
        </div>`;
    }
  }
});

// ── Utility ──────────────────────────────────────────────────────────────────

function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str ?? '')));
  return d.innerHTML;
}

// ── Dark map style ───────────────────────────────────────────────────────────

const DARK_MAP_STYLE = [
  { elementType: 'geometry', stylers: [{ color: '#1d2c4d' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#8ec3b9' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#1a3646' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#304a7d' }] },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#2c6675' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0e1626' }] },
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'administrative', elementType: 'labels', stylers: [{ visibility: 'simplified' }] },
];
