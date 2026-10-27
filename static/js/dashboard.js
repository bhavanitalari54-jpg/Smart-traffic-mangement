/**
 * dashboard.js – Real-time dashboard logic
 * Connects to Flask-SocketIO and updates stat cards + charts on each event.
 */

const socket = io();
let totalVehicles = 0;
const cameraStats = {};

// ── SocketIO Listeners ──────────────────────────────────────────────────────

socket.on('connect', () => {
  console.log('SocketIO connected:', socket.id);
  updateConnectionStatus(true);
});

socket.on('disconnect', () => {
  console.log('SocketIO disconnected');
  updateConnectionStatus(false);
});

socket.on('stats_update', (data) => {
  cameraStats[data.camera_id] = data;
  updateStatsCards();
  updateChartsFromStats(data);
});

socket.on('accident_alert', (alert) => {
  showToast('🚨 Suspected Accident', `Camera: ${alert.camera_name} | Conf: ${alert.confidence_pct}%`, 'accident');
  incrementPendingBadge();
});

socket.on('alert_update', (data) => {
  const icon = data.status === 'confirmed' ? '✅' : '🔕';
  showToast(`${icon} Alert ${data.id}`, `Status: ${data.status}`, 'success');
});

// ── Stats Cards ─────────────────────────────────────────────────────────────

function updateStatsCards() {
  let total = 0;
  let maxDensity = 'LOW';
  const densityOrder = { LOW: 0, MEDIUM: 1, HIGH: 2 };

  for (const cam of Object.values(cameraStats)) {
    total += cam.total || 0;
    if (densityOrder[cam.density] > densityOrder[maxDensity]) {
      maxDensity = cam.density;
    }
  }
  totalVehicles = total;

  const el = document.getElementById('stat-total-vehicles');
  if (el) animateNumber(el, parseInt(el.textContent) || 0, total);

  const densityEl = document.getElementById('stat-density');
  if (densityEl) {
    densityEl.textContent = maxDensity;
    densityEl.className = `stat-value density-${maxDensity.toLowerCase()}`;
  }
}

function animateNumber(el, from, to) {
  const duration = 500;
  const start = performance.now();
  const update = (now) => {
    const t = Math.min((now - start) / duration, 1);
    el.textContent = Math.round(from + (to - from) * easeOut(t));
    if (t < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

// ── Pending Alert Badge ──────────────────────────────────────────────────────

function incrementPendingBadge() {
  const badge = document.getElementById('alert-badge');
  if (badge) {
    const current = parseInt(badge.textContent) || 0;
    badge.textContent = current + 1;
    badge.style.display = 'flex';
  }
}

// ── Connection Status ────────────────────────────────────────────────────────

function updateConnectionStatus(connected) {
  const dot = document.querySelector('.live-dot');
  if (dot) {
    dot.style.background = connected ? 'var(--green)' : 'var(--red)';
  }
}

// ── Toast Notifications ──────────────────────────────────────────────────────

function showToast(title, message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <div class="toast-icon">${type === 'accident' ? '🚨' : type === 'success' ? '✅' : 'ℹ️'}</div>
    <div>
      <div class="toast-title">${escHtml(title)}</div>
      <div class="toast-message">${escHtml(message)}</div>
    </div>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}

// ── Live Clock ───────────────────────────────────────────────────────────────

function startClock() {
  const el = document.getElementById('live-clock');
  if (!el) return;
  const update = () => {
    el.textContent = new Date().toLocaleTimeString('en-IN', { hour12: false });
  };
  update();
  setInterval(update, 1000);
}

// ── Sidebar Toggle ───────────────────────────────────────────────────────────

function initSidebar() {
  const btn = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  if (!btn || !sidebar) return;
  btn.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
    localStorage.setItem('sidebar-collapsed', sidebar.classList.contains('collapsed'));
  });
  if (localStorage.getItem('sidebar-collapsed') === 'true') {
    sidebar.classList.add('collapsed');
  }
}

// ── Periodic API Poll (fallback) ─────────────────────────────────────────────

function startStatsPoll() {
  setInterval(async () => {
    try {
      const r = await fetch('/api/stats');
      if (!r.ok) return;
      const data = await r.json();
      // Update pending alert badge
      const badge = document.getElementById('alert-badge');
      if (badge) {
        const n = data.pending_alerts || 0;
        badge.textContent = n;
        badge.style.display = n > 0 ? 'flex' : 'none';
      }
    } catch (e) { /* network error — ignore */ }
  }, 10000);
}

// ── Escape HTML ──────────────────────────────────────────────────────────────

function escHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

// ── Placeholder chart data injector (overridden by charts.js) ────────────────

function updateChartsFromStats(data) {
  if (typeof window.pushVehicleDataPoint === 'function') {
    window.pushVehicleDataPoint(data.camera_id, data.total, data.density);
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  startClock();
  initSidebar();
  startStatsPoll();
});
