/**
 * charts.js – Chart.js chart initialisation and real-time updates.
 * Requires Chart.js 4.x loaded before this script.
 */

// ── Colour palette ──────────────────────────────────────────────────────────
const PALETTE = {
  cyan:   'rgba(0,212,255,1)',
  cyanBg: 'rgba(0,212,255,0.12)',
  purple: 'rgba(123,47,247,1)',
  green:  'rgba(0,200,83,1)',
  yellow: 'rgba(255,214,0,1)',
  red:    'rgba(244,67,54,1)',
  muted:  'rgba(69,90,122,0.4)',
};

// Common Chart.js defaults
Chart.defaults.color = '#7986cb';
Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";

// ── Shared rolling buffer ────────────────────────────────────────────────────
const MAX_POINTS = 30;
const vehicleHistory = {};   // { cam_id: [counts] }
const densityMap = { LOW: 0, MEDIUM: 1, HIGH: 2 };

window.pushVehicleDataPoint = (camId, total, density) => {
  if (!vehicleHistory[camId]) vehicleHistory[camId] = [];
  vehicleHistory[camId].push(total);
  if (vehicleHistory[camId].length > MAX_POINTS) vehicleHistory[camId].shift();
  updateAllCharts();
};

// ── Helper: rolling labels ───────────────────────────────────────────────────
function rollingLabels(n) {
  return Array.from({ length: n }, (_, i) => `–${n - i - 1}s`);
}

function padArray(arr, len, fill = 0) {
  const out = arr.slice(-len);
  while (out.length < len) out.unshift(fill);
  return out;
}

// ════════════════════════════════════════════════════════════
// VEHICLE COUNT LINE CHART (dashboard)
// ════════════════════════════════════════════════════════════

let vehicleChart = null;

function initVehicleChart() {
  const ctx = document.getElementById('vehicleChart');
  if (!ctx) return;

  vehicleChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: rollingLabels(MAX_POINTS),
      datasets: [
        {
          label: 'Total Vehicles',
          data: new Array(MAX_POINTS).fill(0),
          borderColor: PALETTE.cyan,
          backgroundColor: PALETTE.cyanBg,
          borderWidth: 2.5,
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: PALETTE.cyan,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 400 },
      plugins: {
        legend: { display: false },
        tooltip: {
          mode: 'index',
          intersect: false,
          backgroundColor: 'rgba(10,14,26,0.9)',
          borderColor: 'rgba(0,212,255,0.3)',
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { maxTicksLimit: 6, font: { size: 11 } },
        },
        y: {
          min: 0,
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { font: { size: 11 }, stepSize: 1 },
        },
      },
    },
  });
}

// ════════════════════════════════════════════════════════════
// DENSITY DONUT CHART (dashboard)
// ════════════════════════════════════════════════════════════

let densityChart = null;

function initDensityChart() {
  const ctx = document.getElementById('densityChart');
  if (!ctx) return;

  densityChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Low', 'Medium', 'High'],
      datasets: [{
        data: [1, 0, 0],
        backgroundColor: [PALETTE.green, PALETTE.yellow, PALETTE.red],
        borderColor: 'rgba(10,14,26,0.8)',
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '72%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { padding: 16, usePointStyle: true, pointStyleWidth: 10 },
        },
        tooltip: {
          backgroundColor: 'rgba(10,14,26,0.9)',
          borderColor: 'rgba(0,212,255,0.3)',
          borderWidth: 1,
        },
      },
    },
  });
}

// ════════════════════════════════════════════════════════════
// ROAD-WISE BAR CHART (dashboard / signals)
// ════════════════════════════════════════════════════════════

let roadChart = null;

function initRoadChart(cameraNames, initialData) {
  const ctx = document.getElementById('roadChart');
  if (!ctx) return;

  roadChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: cameraNames,
      datasets: [{
        label: 'Vehicles',
        data: initialData || cameraNames.map(() => 0),
        backgroundColor: [PALETTE.cyanBg, 'rgba(123,47,247,0.12)', 'rgba(0,200,83,0.12)'],
        borderColor: [PALETTE.cyan, PALETTE.purple, PALETTE.green],
        borderWidth: 2,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 500 },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(10,14,26,0.9)',
          borderColor: 'rgba(0,212,255,0.3)',
          borderWidth: 1,
        },
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          min: 0,
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { font: { size: 11 }, stepSize: 1 },
        },
      },
    },
  });
}

// ════════════════════════════════════════════════════════════
// ALERT HISTORY LINE CHART (history page)
// ════════════════════════════════════════════════════════════

function initAlertHistoryChart(labels, pendingData, confirmedData) {
  const ctx = document.getElementById('alertHistoryChart');
  if (!ctx) return;

  new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Pending',
          data: pendingData,
          backgroundColor: 'rgba(255,214,0,0.3)',
          borderColor: PALETTE.yellow,
          borderWidth: 2,
          borderRadius: 4,
        },
        {
          label: 'Confirmed',
          data: confirmedData,
          backgroundColor: 'rgba(244,67,54,0.3)',
          borderColor: PALETTE.red,
          borderWidth: 2,
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'top',
          labels: { usePointStyle: true, padding: 16 },
        },
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          grid: { color: 'rgba(255,255,255,0.04)' },
          ticks: { font: { size: 11 }, stepSize: 1 },
        },
      },
    },
  });
}

// ── Update all charts from live data ────────────────────────────────────────

function updateAllCharts() {
  // Vehicle count: sum all cameras
  if (vehicleChart) {
    let totals = new Array(MAX_POINTS).fill(0);
    for (const arr of Object.values(vehicleHistory)) {
      const padded = padArray(arr, MAX_POINTS);
      totals = totals.map((v, i) => v + (padded[i] || 0));
    }
    vehicleChart.data.datasets[0].data = totals;
    vehicleChart.update('none');
  }

  // Density donut
  if (densityChart) {
    let low = 0, med = 0, high = 0;
    for (const arr of Object.values(vehicleHistory)) {
      const last = arr[arr.length - 1] || 0;
      if (last <= 5) low++;
      else if (last <= 15) med++;
      else high++;
    }
    if (low === 0 && med === 0 && high === 0) low = 1;
    densityChart.data.datasets[0].data = [low, med, high];
    densityChart.update('none');
  }

  // Road-wise bar
  if (roadChart) {
    const counts = Object.values(vehicleHistory).map(arr => arr[arr.length - 1] || 0);
    roadChart.data.datasets[0].data = counts;
    roadChart.update('none');
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  initVehicleChart();
  initDensityChart();

  // Road chart: expect window.CAMERA_NAMES defined in template
  if (window.CAMERA_NAMES) {
    initRoadChart(window.CAMERA_NAMES, window.CAMERA_INITIAL_COUNTS || []);
  }

  // History chart: expect window.ALERT_HISTORY_DATA
  if (window.ALERT_HISTORY_DATA) {
    const { labels, pending, confirmed } = window.ALERT_HISTORY_DATA;
    initAlertHistoryChart(labels, pending, confirmed);
  }
});
