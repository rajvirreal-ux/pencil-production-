'use strict';

// ── State ────────────────────────────────────────────────────────────────────
let currentState = null;
let ws = null;
let wsRetryTimeout = null;
let pollInterval = null;

// ── WebSocket ────────────────────────────────────────────────────────────────
function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onmessage = (evt) => {
    try {
      const data = JSON.parse(evt.data);
      render(data);
    } catch (e) { /* ignore malformed */ }
  };

  ws.onopen = () => {
    clearTimeout(wsRetryTimeout);
    stopPolling();
    setSyncStatus('ok');
  };

  ws.onclose = ws.onerror = () => {
    // Fall back to polling every 2 s while disconnected
    startPolling();
    wsRetryTimeout = setTimeout(connectWS, 5000);
  };
}

function startPolling() {
  if (pollInterval) return;
  pollInterval = setInterval(async () => {
    try {
      const r = await fetch('/api/state');
      const d = await r.json();
      render(d);
    } catch (e) { /* ignore */ }
  }, 2000);
}

function stopPolling() {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
}

// ── API calls ────────────────────────────────────────────────────────────────
async function apiPost(path) {
  try {
    const r = await fetch(path, { method: 'POST' });
    const d = await r.json();
    // State will arrive via WS on next tick; no need to render manually
  } catch (e) {
    console.error('API error', path, e);
  }
}

// ── Health polling ────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const r = await fetch('/health');
    const d = await r.json();
    setSyncStatus(d.influx_sync === 'ok' ? 'ok' : 'warn', d.influx_error);
  } catch (e) {
    setSyncStatus('warn', 'health endpoint unreachable');
  }
}

function setSyncStatus(status, msg) {
  const dot  = document.getElementById('sync-dot');
  const text = document.getElementById('sync-text');
  dot.className = `sync-dot sync-${status}`;
  text.textContent = status === 'ok' ? 'ok' : `degraded — ${msg || ''}`;
}

// ── Rendering ────────────────────────────────────────────────────────────────
function render(state) {
  currentState = state;

  const ms = (state.machine_state || 'STOPPED').toUpperCase();

  // Fault banner
  const faultBanner = document.getElementById('fault-banner');
  const faultText   = document.getElementById('fault-text');
  if (ms === 'FAULTED') {
    faultBanner.classList.remove('hidden');
    faultText.textContent = `MACHINE FAULTED — ${state.fault_reason || ''}`;
  } else {
    faultBanner.classList.add('hidden');
  }

  // State badge
  const badge = document.getElementById('state-badge');
  badge.textContent = ms;
  badge.className   = `machine-state-badge ${ms.toLowerCase()}`;

  // Button states
  const isRunning = ms === 'RUNNING';
  const isStopped = ms === 'STOPPED';
  const isPaused  = ms === 'PAUSED';
  const isFaulted = ms === 'FAULTED';

  document.getElementById('btn-start').disabled  = isRunning || isFaulted;
  document.getElementById('btn-stop').disabled   = isStopped || isFaulted;
  document.getElementById('btn-pause').disabled  = !isRunning;
  const resetBtn = document.getElementById('btn-reset');
  resetBtn.disabled = false;
  resetBtn.className = isFaulted ? 'btn btn-reset fault-reset' : 'btn btn-reset';

  // Counters
  const qc = state.qc || {};
  document.getElementById('cnt-good').textContent      = qc.good ?? 0;
  document.getElementById('cnt-defective').textContent = qc.defective ?? 0;
  document.getElementById('cnt-yield').textContent     = qc.total > 0 ? `${qc.yield_pct}%` : '—';
  document.getElementById('cnt-cycles').textContent    = state.total_cycles ?? 0;

  // CMMS
  const cmms = state.cmms || {};
  document.getElementById('cnt-maint').textContent = cmms.cycles_since_maintenance ?? 0;
  const maintBanner = document.getElementById('maint-banner');
  if (cmms.maintenance_due) {
    maintBanner.classList.remove('hidden');
  } else {
    maintBanner.classList.add('hidden');
  }

  // Stations / conveyor
  renderConveyor(state.stations || []);

  // Defect log
  renderDefectLog(qc.recent_rejects || []);

  // Pareto
  renderPareto(qc.pareto || []);
}

function renderConveyor(stations) {
  const el = document.getElementById('conveyor');
  el.innerHTML = '';
  stations.forEach((s, i) => {
    const stClass = s.state || 'idle';
    const card = document.createElement('div');
    card.className = `station-card ${stClass}`;
    card.innerHTML = `
      <div class="station-num">STATION ${s.id}</div>
      <div class="station-name">${s.name}</div>
      <div class="station-status status-${stClass}">${stClass.toUpperCase()}</div>
      <div class="station-temp">Temp: <span>${s.temperature ?? '—'} °C</span></div>
      <div class="station-val">${paramLabel(s.param_name)}: <span>${s.last_value ?? '—'}</span></div>
      ${s.current_pencil_id ? `<div class="station-pencil">✏ Pencil #${s.current_pencil_id}</div>` : ''}
    `;
    el.appendChild(card);
  });
}

function paramLabel(name) {
  const map = {
    insertion_force_N:   'Force (N)',
    cure_temp_C:         'Cure Temp (°C)',
    crimp_pressure_bar:  'Pressure (bar)',
    insertion_depth_mm:  'Depth (mm)',
  };
  return map[name] || name;
}

function renderDefectLog(rejects) {
  const el = document.getElementById('defect-log');
  if (!rejects || rejects.length === 0) {
    el.innerHTML = '<li class="defect-empty">No rejects yet.</li>';
    return;
  }
  el.innerHTML = rejects.map(r => `
    <li>
      <span class="defect-id">✏ #${r.id} </span>
      <span class="defect-reason">${r.reason || 'UNKNOWN'}</span><br/>
      <span class="defect-detail">${r.summary || r.detail || ''}</span>
    </li>
  `).join('');
}

function renderPareto(pareto) {
  const el = document.getElementById('pareto');
  if (!pareto || pareto.length === 0) {
    el.innerHTML = '<div style="color:var(--text-dim);font-size:0.72rem">No defects yet.</div>';
    return;
  }
  const max = Math.max(...pareto.map(p => p.count), 1);
  el.innerHTML = pareto.map(p => `
    <div class="pareto-row">
      <div class="pareto-key" title="${p.reason}">${p.reason}</div>
      <div class="pareto-bar-wrap">
        <div class="pareto-bar" style="width:${Math.round(100 * p.count / max)}%"></div>
      </div>
      <div class="pareto-cnt">${p.count}</div>
    </div>
  `).join('');
}

// ── Init ─────────────────────────────────────────────────────────────────────
connectWS();
setInterval(checkHealth, 10000);
checkHealth();
