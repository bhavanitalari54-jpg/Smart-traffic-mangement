/**
 * alerts.js – Alert review actions and real-time list updates.
 */

// ── Confirm / Dismiss alert via REST API ────────────────────────────────────

async function confirmAlert(alertId) {
  await updateAlertStatus(alertId, 'confirm');
}

async function dismissAlert(alertId) {
  await updateAlertStatus(alertId, 'dismiss');
}

async function updateAlertStatus(alertId, action) {
  const card = document.getElementById(`alert-card-${alertId}`);
  if (card) {
    card.style.opacity = '0.6';
    card.style.pointerEvents = 'none';
  }

  try {
    const resp = await fetch(`/api/alerts/${alertId}/${action}`, { method: 'POST' });
    const data = await resp.json();

    if (resp.ok && data.success) {
      updateCardStatus(alertId, data.status);
    } else {
      alert(`Error: ${data.error || 'Unknown error'}`);
      if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
    }
  } catch (err) {
    console.error('Alert update failed:', err);
    if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
  }
}

function updateCardStatus(alertId, newStatus) {
  const card = document.getElementById(`alert-card-${alertId}`);
  if (!card) return;

  // Update card class
  card.className = `alert-card ${newStatus} fade-in`;

  // Update status badge
  const badge = card.querySelector('.alert-status-badge');
  if (badge) {
    badge.className = `alert-status-badge ${newStatus}`;
    badge.textContent = newStatus;
  }

  // Hide action buttons
  const actions = card.querySelector('.alert-actions');
  if (actions && newStatus !== 'pending') actions.innerHTML = '';

  card.style.opacity = '1';
  card.style.pointerEvents = '';

  // Update pending count in navbar
  const pendingBadge = document.getElementById('alert-badge');
  if (pendingBadge) {
    const n = Math.max(0, (parseInt(pendingBadge.textContent) || 1) - 1);
    pendingBadge.textContent = n;
    pendingBadge.style.display = n > 0 ? 'flex' : 'none';
  }
}

// ── Real-time: inject new alert card at top of list ─────────────────────────

function prependAlertCard(alert) {
  const list = document.getElementById('alert-list');
  if (!list) return;

  const card = createAlertCard(alert);
  list.insertAdjacentHTML('afterbegin', card);

  // Remove empty-state if present
  const empty = list.querySelector('.empty-state');
  if (empty) empty.remove();
}

function createAlertCard(alert) {
  const confColor = alert.confidence >= 0.7 ? 'var(--red)' : alert.confidence >= 0.4 ? 'var(--yellow)' : 'var(--text-muted)';
  return `
  <div class="alert-card pending fade-in" id="alert-card-${escapeId(alert.id)}">
    <div class="alert-header">
      <span class="alert-id">#${escHtml(alert.id)}</span>
      <span class="alert-status-badge pending">Pending</span>
    </div>
    <div class="alert-body">
      <div class="alert-meta">
        📷 <strong>${escHtml(alert.camera_name)}</strong> &nbsp;|&nbsp;
        🛣️ ${escHtml(alert.road)} &nbsp;|&nbsp;
        🕐 ${escHtml(alert.timestamp_str)}
      </div>
      <div class="alert-meta">
        ⚡ Trigger: <strong>${escHtml(alert.trigger)}</strong> &nbsp;|&nbsp;
        Confidence: <strong style="color:${confColor}">${alert.confidence_pct}%</strong>
      </div>
      <div class="disclaimer-box" style="margin-bottom:12px;">
        ⚠️ This is a <strong>suspected</strong> event detected by automated heuristics.
        Human review is required before any emergency response.
      </div>
      <div class="alert-actions">
        <button class="btn btn-red btn-sm" onclick="confirmAlert('${escapeId(alert.id)}')">
          🚨 Confirm Accident
        </button>
        <button class="btn btn-muted btn-sm" onclick="dismissAlert('${escapeId(alert.id)}')">
          ✖ Dismiss
        </button>
      </div>
    </div>
  </div>`;
}

// ── Snapshot modal ───────────────────────────────────────────────────────────

async function viewSnapshot(alertId) {
  try {
    const resp = await fetch(`/api/alerts/${alertId}`);
    const alert = await resp.json();
    const modal = document.getElementById('snapshot-modal');
    if (!modal) return;
    const img = modal.querySelector('#snapshot-img');
    const title = modal.querySelector('#snapshot-title');
    if (title) title.textContent = `Alert #${alert.id} — ${alert.camera_name}`;
    if (img && alert.snapshot) {
      img.src = `data:image/jpeg;base64,${alert.snapshot}`;
    } else if (img) {
      img.src = '';
      img.alt = 'No snapshot available';
    }
    modal.style.display = 'flex';
  } catch (err) {
    console.error('Failed to load snapshot:', err);
  }
}

function closeSnapshotModal() {
  const modal = document.getElementById('snapshot-modal');
  if (modal) modal.style.display = 'none';
}

// ── Filter buttons ───────────────────────────────────────────────────────────

function filterAlerts(status) {
  document.querySelectorAll('.alert-card').forEach(card => {
    if (!status || card.classList.contains(status)) {
      card.style.display = '';
    } else {
      card.style.display = 'none';
    }
  });
  // Highlight active button
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.classList.toggle('btn-accent', btn.dataset.filter === (status || ''));
    btn.classList.toggle('btn-outline', btn.dataset.filter !== (status || ''));
  });
}

// ── SocketIO: inject new alerts in real time ─────────────────────────────────

if (typeof socket !== 'undefined') {
  socket.on('accident_alert', (alert) => {
    prependAlertCard(alert);
  });

  socket.on('alert_update', (data) => {
    updateCardStatus(data.id, data.status);
  });
}

// ── CSV Export ───────────────────────────────────────────────────────────────

async function exportCSV() {
  try {
    const resp = await fetch('/api/history');
    const alerts = await resp.json();
    if (!alerts.length) { alert('No data to export.'); return; }

    const cols = ['id','camera_id','camera_name','road','status','confidence_pct','trigger','timestamp_str'];
    const header = cols.join(',');
    const rows = alerts.map(a => cols.map(c => `"${String(a[c] ?? '').replace(/"/g,'""')}"`).join(','));
    const csv = [header, ...rows].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `traffic_alerts_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert('Export failed: ' + err.message);
  }
}

// ── Utility ──────────────────────────────────────────────────────────────────

function escHtml(str) {
  const d = document.createElement('div');
  d.appendChild(document.createTextNode(String(str ?? '')));
  return d.innerHTML;
}

function escapeId(str) {
  return String(str).replace(/[^a-zA-Z0-9_-]/g, '_');
}

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Default filter: all
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => filterAlerts(btn.dataset.filter || ''));
  });

  // Close modal on backdrop click
  const modal = document.getElementById('snapshot-modal');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeSnapshotModal();
    });
  }
});
