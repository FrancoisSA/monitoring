"""
dashboard.py — Template HTML du dashboard Pi Monitor.
"""

HTML_DASHBOARD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pi Monitor</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3e;
  --text: #e0e0f0; --muted: #7878a0; --accent: #4fc3f7;
  --green: #81c784; --orange: #ffb74d; --red: #f06292;
}
body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; font-size: 14px; }
header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 14px 24px; display: flex; align-items: center; gap: 16px; }
header h1 { font-size: 17px; font-weight: 600; }
header h1 span { color: var(--accent); }
.meta { margin-left: auto; font-size: 12px; color: var(--muted); text-align: right; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--green); margin-right: 5px; vertical-align: middle; }
.tabs { display: flex; padding: 0 24px; background: var(--surface); border-bottom: 1px solid var(--border); }
.tab { padding: 12px 20px; font-size: 13px; cursor: pointer; color: var(--muted); border-bottom: 2px solid transparent; transition: color .15s; user-select: none; }
.tab:hover { color: var(--text); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.tab-content { display: none; }
.tab-content.active { display: block; }
.main { padding: 24px; display: flex; flex-direction: column; gap: 20px; }
.kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; }
.kpi { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 16px 20px; }
.kpi .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }
.kpi .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.kpi .sub { color: var(--muted); font-size: 12px; margin-top: 2px; }
.kpi .bar-wrap { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-top: 8px; }
.kpi .bar-fill { height: 100%; border-radius: 3px; transition: width .4s; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 20px; }
.card-title { font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; margin-bottom: 16px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
@media (max-width: 800px) { .two-col { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 8px 12px; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; color: var(--muted); border-bottom: 1px solid var(--border); }
td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(255,255,255,.03); }
.empty { text-align: center; color: var(--muted); padding: 30px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.ok   { background: rgba(129,199,132,.15); color: var(--green); }
.warn { background: rgba(255,183,77,.15);  color: var(--orange); }
.err  { background: rgba(240,98,146,.15);  color: var(--red); }
.btn { padding: 4px 10px; border-radius: 5px; border: none; font-size: 12px; cursor: pointer; font-weight: 500; margin-left: 3px; }
.btn-start   { background: transparent; border: 1px solid var(--green);  color: var(--green); }
.btn-stop    { background: transparent; border: 1px solid var(--red);    color: var(--red); }
.btn-restart { background: transparent; border: 1px solid var(--orange); color: var(--orange); }
.btn:disabled { opacity: .4; }
.bar-wrap2 { display: flex; align-items: center; gap: 8px; }
.bar2 { flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; }
.bar2-fill { height: 100%; border-radius: 3px; }
.bar2-pct { font-size: 12px; color: var(--muted); min-width: 38px; text-align: right; }
.alert { background: rgba(240,98,146,.15); border: 1px solid rgba(240,98,146,.4); border-radius: 8px; padding: 10px 16px; font-size: 13px; color: var(--red); }
canvas { display: block; width: 100%; height: 100px; background: var(--border); border-radius: 6px; margin-top: 8px; }
.cfg-label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 5px; display: block; }
.cfg-input { background: var(--bg); border: 1px solid var(--border); color: var(--text); border-radius: 5px; padding: 7px 10px; font-size: 14px; width: 100%; outline: none; }
.cfg-input:focus { border-color: var(--accent); }
.cfg-hint { color: var(--muted); font-size: 11px; margin-top: 3px; }
</style>
</head>
<body>

<header>
  <h1>Pi <span>Monitor</span> <small style="color: var(--muted); font-size: 11px;">v{{ version }}</small></h1>
  <div class="meta">
    <div><span class="dot" id="dot"></span><span id="hostname">FSA-PI5</span></div>
    <div id="uptime" style="margin-top:3px">—</div>
    <div id="ts" style="margin-top:3px">Chargement...</div>
    <div style="margin-top:10px;">
      <button id="temp-toggle" style="padding: 4px 8px; font-size: 12px; background: var(--bg2); border: 1px solid var(--border); border-radius: 4px; cursor: pointer;" onclick="toggleTempMonitoring()">
        <span id="temp-toggle-text">🌡 Temp: ON</span>
      </button>
    </div>
  </div>
</header>

<div class="tabs">
  <div class="tab active"  onclick="tab('overview',this)">Vue d'ensemble</div>
  <div class="tab"         onclick="tab('procs',this)">Processus</div>
  <div class="tab"         onclick="tab('services',this)">Services</div>
  <div class="tab"         onclick="tab('voltage',this)">Tension</div>
  <div class="tab"         onclick="tab('wifi',this)">WiFi <span id="wifi-alert-badge" style="display:none;background:var(--red);color:#fff;border-radius:10px;font-size:10px;padding:1px 6px;vertical-align:middle;font-weight:700">!</span></div>
  <div class="tab"         onclick="tab('smb',this)">Partages</div>
  <div class="tab"         onclick="tab('disk',this)">Analyse disque</div>
</div>

<div id="tab-overview" class="tab-content active"><div class="main">
  <div class="kpi-row">
    <div class="kpi">
      <div class="label">CPU</div>
      <div class="value" id="v-cpu">—</div>
      <div class="sub"  id="v-temp">—</div>
      <div class="bar-wrap"><div class="bar-fill" id="b-cpu"></div></div>
    </div>
    <div class="kpi">
      <div class="label">Memoire</div>
      <div class="value" id="v-mem">—</div>
      <div class="sub"  id="v-mem2">—</div>
      <div class="bar-wrap"><div class="bar-fill" id="b-mem"></div></div>
    </div>
    <div class="kpi">
      <div class="label">Tension coeur</div>
      <div class="value" id="v-volt">—</div>
      <div class="sub"  id="v-volt2">—</div>
    </div>
    <div class="kpi">
      <div class="label">Reseau RX</div>
      <div class="value" id="v-rx">—</div>
      <div class="sub"  id="v-tx">TX: —</div>
    </div>
  </div>
  <div id="volt-alert" style="display:none" class="alert"></div>
  <div class="two-col">
    <div class="card">
      <div class="card-title">Disques</div>
      <table><thead><tr><th>Montage</th><th>Type</th><th>Utilisation</th><th style="text-align:right">Libre</th></tr></thead>
      <tbody id="t-disks"></tbody></table>
    </div>
    <div class="card">
      <div class="card-title">Flux I/O</div>
      <table><thead><tr><th>Flux</th><th style="text-align:right">Debit</th></tr></thead>
      <tbody id="t-io"></tbody></table>
    </div>
  </div>
</div></div>

<div id="tab-procs" class="tab-content"><div class="main">
  <div class="card">
    <div class="card-title">Top processus CPU</div>
    <table><thead><tr><th>Nom</th><th style="text-align:right">PID</th><th>CPU %</th><th>RAM %</th></tr></thead>
    <tbody id="t-procs"></tbody></table>
  </div>
</div></div>

<div id="tab-services" class="tab-content"><div class="main">
  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;gap:8px">
      Services systemd
      <span id="svc-updated" style="font-size:11px;font-weight:400;color:var(--muted)"></span>
      <button id="svc-refresh-btn" onclick="refreshServices()"
        style="margin-left:auto;padding:2px 10px;font-size:11px;background:var(--card);border:1px solid var(--muted);color:var(--muted);border-radius:4px;cursor:pointer">
        Rafraichir</button>
    </div>
    <table><thead><tr><th>Service</th><th>Port</th><th>Etat</th><th>Depuis</th><th>Actions</th></tr></thead>
    <tbody id="t-svc"></tbody></table>
  </div>
  <div class="card">
    <div class="card-title">Serveurs HTTP</div>
    <table><thead><tr><th>Nom</th><th>URL</th><th>Statut</th><th style="text-align:right">ms</th></tr></thead>
    <tbody id="t-http"></tbody></table>
  </div>
</div></div>

<div id="tab-voltage" class="tab-content"><div class="main">
  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Tension actuelle</div>
      <div class="value" id="v-volt-big">—</div>
      <div class="sub"  id="v-volt-flags">—</div>
    </div>
    <div class="kpi">
      <div class="label">Evenements (heure)</div>
      <div class="value" id="v-volt-events">0</div>
      <div class="sub">sous-tension detectee</div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Historique tension</div>
    <canvas id="volt-canvas"></canvas>
  </div>
  <div class="card">
    <div class="card-title">Evenements</div>
    <table><thead><tr><th>Heure</th><th>Tension</th><th>CPU</th></tr></thead>
    <tbody id="t-uvolt"></tbody></table>
  </div>
</div></div>

<div id="tab-wifi" class="tab-content"><div class="main">
  <div class="kpi-row">
    <div class="kpi">
      <div class="label">Interface wlan0</div>
      <div class="value" id="wifi-state" style="font-size:18px">—</div>
      <div class="sub"   id="wifi-ip">—</div>
    </div>
    <div class="kpi">
      <div class="label">Réseaux visibles</div>
      <div class="value" id="wifi-count">—</div>
      <div class="sub">mis à jour toutes les 30s</div>
    </div>
    <div class="kpi">
      <div class="label">Meilleur signal</div>
      <div class="value" id="wifi-best-signal">—</div>
      <div class="sub"   id="wifi-best-ssid">—</div>
    </div>
    <div class="kpi">
      <div class="label">Surveillés</div>
      <div class="value" id="wifi-mon-count" style="font-size:24px">0</div>
      <div class="sub">SSIDs en monitoring</div>
    </div>
  </div>

  <!-- Panneaux de monitoring — un par SSID surveillé, générés dynamiquement -->
  <div id="wifi-monitors"></div>

  <div class="card">
    <div class="card-title" style="display:flex;align-items:center;justify-content:space-between">
      <span>Réseaux WiFi détectés <span id="wifi-net-count" style="color:var(--muted);font-weight:400"></span></span>
      <button id="wifi-rescan-btn" onclick="rescanWifiTable()"
        style="padding:3px 10px;background:transparent;border:1px solid var(--muted);border-radius:5px;color:var(--muted);font-size:11px;cursor:pointer;font-weight:500">
        Rafraîchir
      </button>
    </div>
    <div id="wifi-rescan-status" style="font-size:11px;color:var(--muted);margin-bottom:6px;min-height:14px"></div>
    <table>
      <thead><tr>
        <th></th>
        <th>SSID</th>
        <th>Bande</th>
        <th>Canal</th>
        <th>Signal</th>
        <th>Qualité</th>
        <th>Débit max</th>
        <th>Sécurité</th>
        <th></th>
      </tr></thead>
      <tbody id="t-wifi"></tbody>
    </table>
  </div>

  <!-- Paramètres de surveillance WiFi -->
  <div class="card" id="wifi-cfg-card">
    <div class="card-title" style="display:flex;align-items:center;gap:10px">
      <span>Paramètres de surveillance</span>
      <span id="cfg-status" style="font-size:12px;font-weight:400;text-transform:none;letter-spacing:0"></span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:16px">
      <div>
        <label class="cfg-label" for="cfg-scan-interval">Intervalle de scan</label>
        <input class="cfg-input" id="cfg-scan-interval" type="number" min="5" max="3600" placeholder="30">
        <div class="cfg-hint">secondes (min 5)</div>
      </div>
      <div>
        <label class="cfg-label" for="cfg-history-min">Historique conservé</label>
        <input class="cfg-input" id="cfg-history-min" type="number" min="1" max="1440" placeholder="30">
        <div class="cfg-hint">minutes</div>
      </div>
      <div>
        <label class="cfg-label" for="cfg-alert-threshold">Seuil d'alerte</label>
        <input class="cfg-input" id="cfg-alert-threshold" type="number" min="1" max="100" placeholder="20">
        <div class="cfg-hint">points de chute de signal</div>
      </div>
      <div>
        <label class="cfg-label" for="cfg-alert-window">Fenêtre de moyenne</label>
        <input class="cfg-input" id="cfg-alert-window" type="number" min="2" max="60" placeholder="5">
        <div class="cfg-hint">nombre d'échantillons</div>
      </div>
      <div>
        <label class="cfg-label" for="cfg-latency-threshold">Seuil alerte latence</label>
        <input class="cfg-input" id="cfg-latency-threshold" type="number" min="5" max="5000" placeholder="100">
        <div class="cfg-hint">ms (dépassement → alerte)</div>
      </div>
    </div>
    <div style="border-top:1px solid var(--border);padding-top:16px;margin-top:4px">
      <div class="card-title" style="margin-bottom:12px">Test de téléchargement</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:16px">
        <div>
          <label class="cfg-label" for="cfg-dl-enabled">Activé</label>
          <select class="cfg-input" id="cfg-dl-enabled">
            <option value="0">Non</option>
            <option value="1">Oui</option>
          </select>
        </div>
        <div>
          <label class="cfg-label" for="cfg-dl-url">URL de téléchargement</label>
          <input class="cfg-input" id="cfg-dl-url" type="text" placeholder="http://192.168.1.60:9090/api/speedtest">
          <div class="cfg-hint">laisser vide = endpoint local Pi</div>
        </div>
        <div>
          <label class="cfg-label" for="cfg-dl-size">Taille du test</label>
          <input class="cfg-input" id="cfg-dl-size" type="number" min="64" max="10240" placeholder="1024">
          <div class="cfg-hint">Ko (64 – 10240)</div>
        </div>
        <div>
          <label class="cfg-label" for="cfg-dl-interval">Intervalle</label>
          <input class="cfg-input" id="cfg-dl-interval" type="number" min="30" max="86400" placeholder="300">
          <div class="cfg-hint">secondes entre deux tests</div>
        </div>
      </div>
    </div>
    <button onclick="saveWifiConfig()"
      style="padding:6px 18px;background:var(--accent);border:none;border-radius:5px;color:#000;font-weight:600;font-size:13px;cursor:pointer">
      Sauvegarder
    </button>
  </div>
</div></div>

<div id="tab-smb" class="tab-content"><div class="main">
  <div class="kpi-row" id="samba-kpi">
    <div class="kpi">
      <div class="label">smbd</div>
      <div class="value" id="v-smbd" style="font-size:18px">—</div>
    </div>
    <div class="kpi">
      <div class="label">nmbd</div>
      <div class="value" id="v-nmbd" style="font-size:18px">—</div>
    </div>
    <div class="kpi" style="flex:0 0 auto;align-self:center">
      <button id="samba-restart-btn" onclick="restartSamba()"
        style="padding:8px 18px;background:var(--accent);border:none;border-radius:6px;color:#000;font-weight:600;cursor:pointer;font-size:13px">
        ↺ Relancer Samba
      </button>
      <div id="samba-restart-msg" style="font-size:11px;color:var(--muted);margin-top:4px;text-align:center"></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Partages Samba</div>
    <table><thead><tr><th>Partage</th><th>Chemin</th><th>URL</th></tr></thead>
    <tbody id="t-smb"></tbody></table>
  </div>
  <div class="card" id="samba-watchdog-card" style="display:none">
    <div class="card-title">Journal du watchdog Samba
      <span style="font-size:12px;font-weight:400;color:var(--muted)"> — redémarrages automatiques (6h)</span>
    </div>
    <table><thead><tr><th>Heure</th><th>Service</th><th>Action</th></tr></thead>
    <tbody id="t-samba-watchdog"></tbody></table>
  </div>
</div></div>

<div id="tab-disk" class="tab-content"><div class="main">
  <div class="card">
    <div class="card-title">Analyse de l'espace disque</div>
    <div style="margin-bottom: 16px;">
      <select id="disk-select" style="padding: 8px; border-radius: 5px; border: 1px solid var(--border); background: var(--surface); color: var(--text);">
        <option value="">Sélectionnez un disque</option>
      </select>
      <button id="scan-btn" style="margin-left: 10px; padding: 8px 16px; background: var(--accent); border: none; border-radius: 5px; color: #000; cursor: pointer; font-weight: 600;" onclick="scanDisk()">Analyser</button>
      <span id="scan-status" style="margin-left: 15px; color: var(--muted); font-size: 13px;"></span>
    </div>
    <div id="scan-results"></div>
  </div>
</div></div>

<script>
// ── Monitoring de température ──────────────────────────────────────────────────
var monitorTemperature = true;

// Bascule le monitoring de température côté serveur via l'API
async function toggleTempMonitoring() {
  monitorTemperature = !monitorTemperature;
  var state = monitorTemperature ? 'on' : 'off';
  try {
    await fetch('/api/temperature/' + state, { method: 'POST' });
  } catch(e) {
    console.error('Erreur toggle température:', e);
  }
  var textEl = document.getElementById('temp-toggle-text');
  var btnEl  = document.getElementById('temp-toggle');
  if (monitorTemperature) {
    textEl.textContent = '🌡 Temp: ON';
    btnEl.style.background = 'var(--surface)';
  } else {
    textEl.textContent = '🌡 Temp: OFF';
    btnEl.style.background = '#444';
    document.getElementById('v-temp').textContent = '—';
  }
}

// ── Monitoring WiFi multi-SSID ─────────────────────────────────────────────────
// Ensemble des SSIDs actuellement surveillés (synchronisé avec le serveur)
var _monitoredSsids = new Set();
// Dernière liste de réseaux détectés (mise à jour par load())
var _lastWifiNets = [];
// Top 10 réseaux sans filtre — utilisé par la modale
var _lastAllNets = [];

// Bascule la surveillance d'un SSID (ajoute si absent, retire si présent)
async function toggleMonitorSsid(ssid) {
  var watching = _monitoredSsids.has(ssid);
  var newWatch  = !watching;
  try {
    await fetch('/api/wifi/monitor', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ssid: ssid, watch: newWatch})
    });
    if (newWatch) { _monitoredSsids.add(ssid); }
    else          { _monitoredSsids.delete(ssid); }
  } catch(e) {
    console.error('Erreur toggle WiFi monitor:', e);
  }
}

// Formate une durée en secondes → "2min 15s" ou "1h 3min"
function fmtDuration(s) {
  if (!s && s !== 0) return '—';
  if (s < 60)   return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'min ' + (s % 60) + 's';
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'min';
}

// Couleur selon le niveau de signal (0–100 %)
function sigColor(sig) {
  return sig >= 75 ? 'var(--green)' : sig >= 50 ? 'var(--orange)' : 'var(--red)';
}

// Dessine le sparkline de latence WiFi (valeurs en ms) sur un canvas identifié par canvasId
function drawLatencySparkline(history, canvasId) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !history || history.length < 2) return;
  var ctx = canvas.getContext('2d');
  var w   = canvas.offsetWidth || 600;
  canvas.width = w; canvas.height = 80;
  ctx.clearRect(0, 0, w, 80);

  var values = history.map(function(h) { return h.latency_ms; });
  var mn = 0;
  var mx = Math.max.apply(null, values) * 1.15 || 10;
  var rng = mx - mn || 1;

  // Zone de remplissage sous la courbe
  ctx.beginPath();
  history.forEach(function(h, i) {
    var x = i / (history.length - 1) * w;
    var y = 74 - ((h.latency_ms - mn) / rng) * 68;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w, 74); ctx.lineTo(0, 74); ctx.closePath();
  ctx.fillStyle = 'rgba(255,183,77,.12)';
  ctx.fill();

  // Ligne de latence
  ctx.beginPath();
  ctx.strokeStyle = '#ffb74d'; ctx.lineWidth = 2;
  history.forEach(function(h, i) {
    var x = i / (history.length - 1) * w;
    var y = 74 - ((h.latency_ms - mn) / rng) * 68;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Étiquettes heure (première et dernière) + valeur max
  ctx.fillStyle = '#888'; ctx.font = '10px sans-serif';
  if (history[0])
    ctx.fillText(history[0].time, 4, 76);
  if (history[history.length - 1])
    ctx.fillText(history[history.length - 1].time, w - 32, 76);
  ctx.fillStyle = '#ffb74d';
  ctx.fillText(Math.round(Math.max.apply(null, values)) + ' ms max', w / 2 - 20, 12);
}

// Dessine le sparkline du signal WiFi sur un canvas identifié par canvasId
function drawWifiSparkline(history, canvasId) {
  var canvas = document.getElementById(canvasId);
  if (!canvas || !history || history.length < 2) return;
  var ctx = canvas.getContext('2d');
  var w   = canvas.offsetWidth || 600;
  canvas.width = w; canvas.height = 80;
  ctx.clearRect(0, 0, w, 80);

  // Zone de remplissage sous la courbe
  ctx.beginPath();
  history.forEach(function(h, i) {
    var x = i / (history.length - 1) * w;
    var y = 74 - (h.signal / 100) * 68;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w, 74); ctx.lineTo(0, 74); ctx.closePath();
  ctx.fillStyle = 'rgba(79,195,247,.12)';
  ctx.fill();

  // Ligne du signal
  ctx.beginPath();
  ctx.strokeStyle = '#4fc3f7'; ctx.lineWidth = 2;
  history.forEach(function(h, i) {
    var x = i / (history.length - 1) * w;
    var y = 74 - (h.signal / 100) * 68;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Étiquettes heure (première et dernière)
  ctx.fillStyle = '#888'; ctx.font = '10px sans-serif';
  if (history[0])
    ctx.fillText(history[0].time, 4, 76);
  if (history[history.length - 1])
    ctx.fillText(history[history.length - 1].time, w - 32, 76);
}

// Construit le HTML d'un panneau de monitoring pour un SSID donné
// wMon = wifi_monitor global (contient ping_wlan0, download_enabled, etc.)
function buildMonPanel(ssid, sData, wMon, idx) {
  var ping = wMon.ping || {};
  var history  = sData.history  || [];
  var outages  = sData.outages  || [];
  var alert    = sData.alert;
  var sig      = sData.current_signal;  // null = SSID invisible (coupure)
  var rate     = sData.current_rate;
  var isDown   = sig === null;

  // Dernière coupure en cours ?
  var lastOutage   = outages.length > 0 ? outages[outages.length - 1] : null;
  var activeOutage = lastOutage && lastOutage.end_ts === null;

  // Durée de la coupure en cours (calculée côté client)
  var downDuration = '';
  if (activeOutage && lastOutage.start_ts) {
    var elapsed = Math.floor(Date.now() / 1000 - lastOutage.start_ts);
    downDuration = ' depuis ' + fmtDuration(elapsed);
  }

  // Titre du panneau
  var titleHtml = '<div class="card-title" style="display:flex;align-items:center;gap:12px;margin-bottom:12px">';
  if (isDown) {
    titleHtml += '<span style="color:var(--red);font-size:13px;font-weight:700">⬤ HORS LIGNE' + (downDuration ? ' ' + downDuration : '') + '</span> ';
  }
  titleHtml += '<span>Surveillance\u00a0: <strong>' + ssid + '</strong></span>';
  titleHtml += '<button onclick="toggleMonitorSsid(this.dataset.ssid)" data-ssid="' + ssid.replace(/"/g, '&quot;') + '" '
    + 'style="margin-left:auto;padding:3px 10px;border-radius:4px;border:1px solid var(--red);'
    + 'color:var(--red);background:transparent;cursor:pointer;font-size:12px">Arrêter</button>';
  titleHtml += '</div>';

  // Alerte chute de signal
  var alertHtml = alert
    ? '<div class="alert" style="margin-bottom:12px">⚠ Chute de signal détectée — débit probablement dégradé</div>'
    : '';

  // Alerte latence élevée
  var latAlert    = sData.latency_alert;
  var latAlertHtml = latAlert
    ? '<div class="alert" style="margin-bottom:12px">⚠ Latence élevée détectée (' + (lat !== null ? lat + ' ms' : '?') + ')</div>'
    : '';

  // KPIs
  var sigText  = sig !== null ? sig + '%' : '—';
  var sigClr   = sig !== null ? sigColor(sig) : 'var(--red)';
  var qualText = sig !== null
    ? (sig >= 75 ? 'Excellent' : sig >= 50 ? 'Bon' : sig >= 25 ? 'Faible' : 'Très faible')
    : 'Hors ligne';

  var pingMs  = ping && ping.latency_ms ? ping.latency_ms : null;
  var pingClr = ping && ping.ok
    ? (pingMs < 20 ? 'var(--green)' : pingMs < 80 ? 'var(--orange)' : 'var(--red)')
    : 'var(--red)';

  // Latence WiFi (ping via wlan0)
  var lat    = sData.latency_ms;
  var latClr = lat !== null
    ? (lat < 10 ? 'var(--green)' : lat < 40 ? 'var(--orange)' : 'var(--red)')
    : 'var(--muted)';

  // Débit réel (dernier test de téléchargement)
  var dlResult  = sData.download;
  var dlSpeed   = dlResult && dlResult.ok ? dlResult.speed_mbps : null;
  var dlTime    = dlResult ? dlResult.time : null;
  var dlClr     = dlSpeed !== null
    ? (dlSpeed >= 20 ? 'var(--green)' : dlSpeed >= 5 ? 'var(--orange)' : 'var(--red)')
    : 'var(--muted)';

  var kpiHtml = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:16px">'
    + '<div class="kpi"><div class="label">Signal actuel</div>'
    + '<div class="value" style="font-size:24px;color:' + sigClr + '">' + sigText + '</div>'
    + '<div class="sub">' + qualText + '</div></div>'

    + '<div class="kpi"><div class="label">Latence WiFi</div>'
    + '<div class="value" style="font-size:24px;color:' + latClr + '">'
    + (lat !== null ? lat + ' ms' : '—') + '</div>'
    + '<div class="sub">ping via wlan0</div></div>'

    + '<div class="kpi"><div class="label">Débit annoncé</div>'
    + '<div class="value" style="font-size:20px">' + (rate || '—') + '</div>'
    + '<div class="sub">théorique 802.11</div></div>'

    + (wMon.download_enabled
      ? '<div class="kpi"><div class="label">Débit réel</div>'
        + '<div class="value" style="font-size:22px;color:' + dlClr + '">'
        + (dlSpeed !== null ? dlSpeed + ' MB/s' : '—') + '</div>'
        + '<div class="sub">' + (dlTime ? 'à ' + dlTime : 'en attente…') + '</div></div>'
      : '')

    + '<div class="kpi"><div class="label">Ping gateway</div>'
    + '<div class="value" style="font-size:24px;color:' + pingClr + '">'
    + (pingMs ? pingMs + ' ms' : '—') + '</div>'
    + '<div class="sub">' + (ping && ping.ip ? 'via ' + ping.ip : 'Non joignable') + '</div></div>'

    + '<div class="kpi"><div class="label">Échantillons</div>'
    + '<div class="value" style="font-size:24px">' + history.length + '</div>'
    + '<div class="sub">sur ' + (wMon.download_enabled ? '' : '30 ') + 'min max</div></div>'
    + '</div>';

  // Sparklines (signal + latence) avec IDs uniques
  var canvasId    = 'wifi-canvas-' + idx;
  var latCanvasId = 'latency-canvas-' + idx;
  var sparkHtml = '<div class="card-title">Signal (30 min)</div>'
    + '<canvas id="' + canvasId + '" style="height:80px;margin-bottom:16px"></canvas>'
    + '<div class="card-title" style="margin-top:4px">Latence WiFi (30 min)</div>'
    + '<canvas id="' + latCanvasId + '" style="height:80px;margin-bottom:16px"></canvas>';

  // Journal des coupures (ordre anti-chronologique)
  var outHtml = '';
  for (var i = outages.length - 1; i >= 0; i--) {
    var o = outages[i];
    var dur = o.end_ts !== null
      ? fmtDuration(o.duration_s)
      : '<span style="color:var(--red);font-weight:700">En cours</span>';
    outHtml += '<tr>'
      + '<td style="color:var(--muted)">' + o.start_time + '</td>'
      + '<td style="color:var(--muted)">' + (o.end_time || '—') + '</td>'
      + '<td>' + dur + '</td>'
      + '</tr>';
  }
  var outageSection = outages.length > 0
    ? '<div class="card-title">Journal des coupures</div>'
      + '<table><thead><tr><th>Début</th><th>Fin</th><th>Durée</th></tr></thead>'
      + '<tbody>' + outHtml + '</tbody></table>'
    : '<div style="color:var(--muted);font-size:12px;margin-top:4px">Aucune coupure enregistrée</div>';

  // Journal des alertes de chute de signal
  var alertEvents = sData.alert_events || [];
  var alertEvHtml = '';
  for (var j = alertEvents.length - 1; j >= 0; j--) {
    var ae = alertEvents[j];
    alertEvHtml += '<tr>'
      + '<td style="color:var(--muted)">' + ae.time + '</td>'
      + '<td style="color:var(--red);font-weight:700">' + ae.signal + '%</td>'
      + '<td style="color:var(--muted)">moy. ' + ae.avg_signal + '%</td>'
      + '<td style="color:var(--orange)">−' + ae.drop_pts + ' pts</td>'
      + '</tr>';
  }
  var alertSection = '<div class="card-title" style="margin-top:16px">Journal des alertes signal</div>'
    + (alertEvHtml
      ? '<table><thead><tr><th>Heure</th><th>Signal</th><th>Moyenne</th><th>Chute</th></tr></thead>'
        + '<tbody>' + alertEvHtml + '</tbody></table>'
      : '<div style="color:var(--muted);font-size:12px;margin-top:4px">Aucune alerte enregistrée</div>');

  // Journal des alertes latence
  var latAlertEvents = sData.latency_alert_events || [];
  var latAlertEvHtml = '';
  for (var k = latAlertEvents.length - 1; k >= 0; k--) {
    var lae = latAlertEvents[k];
    latAlertEvHtml += '<tr>'
      + '<td style="color:var(--muted)">' + lae.time + '</td>'
      + '<td style="color:var(--red);font-weight:700">' + lae.latency_ms + ' ms</td>'
      + '</tr>';
  }
  var latAlertSection = '<div class="card-title" style="margin-top:16px">Journal des alertes latence</div>'
    + (latAlertEvHtml
      ? '<table><thead><tr><th>Heure</th><th>Latence</th></tr></thead>'
        + '<tbody>' + latAlertEvHtml + '</tbody></table>'
      : '<div style="color:var(--muted);font-size:12px;margin-top:4px">Aucune alerte latence enregistrée</div>');

  return '<div class="card" style="border-color:' + (isDown ? 'rgba(240,98,146,.4)' : 'var(--border)') + '">'
    + titleHtml + alertHtml + latAlertHtml + kpiHtml + sparkHtml + outageSection + alertSection + latAlertSection
    + '</div>';
}

// ── Configuration WiFi ─────────────────────────────────────────────────────────

// Charge les valeurs courantes depuis le serveur et les injecte dans le formulaire
async function loadWifiConfig() {
  try {
    var d = await fetch('/api/config').then(function(r) { return r.json(); });
    var w = d.wifi || {};
    document.getElementById('cfg-scan-interval').value   = w.scan_interval_s    || 30;
    document.getElementById('cfg-history-min').value     = w.history_minutes     || 30;
    document.getElementById('cfg-alert-threshold').value  = w.alert_threshold_pts        || 20;
    document.getElementById('cfg-alert-window').value     = w.alert_window               || 5;
    document.getElementById('cfg-latency-threshold').value = w.latency_alert_threshold_ms || 100;
    var dl = w.download || {};
    document.getElementById('cfg-dl-enabled').value   = dl.enabled   ? '1' : '0';
    document.getElementById('cfg-dl-url').value        = dl.url       || '';
    document.getElementById('cfg-dl-size').value       = dl.size_kb   || 1024;
    document.getElementById('cfg-dl-interval').value   = dl.interval_s || 300;
  } catch(e) {
    console.error('Erreur chargement config WiFi:', e);
  }
}

// Sauvegarde les paramètres et les applique immédiatement côté serveur
async function saveWifiConfig() {
  var status = document.getElementById('cfg-status');
  var scanInt  = parseInt(document.getElementById('cfg-scan-interval').value,    10);
  var histMin  = parseInt(document.getElementById('cfg-history-min').value,      10);
  var alertThr = parseInt(document.getElementById('cfg-alert-threshold').value,  10);
  var alertWin = parseInt(document.getElementById('cfg-alert-window').value,     10);
  var latThr   = parseInt(document.getElementById('cfg-latency-threshold').value,10);
  var dlSize   = parseInt(document.getElementById('cfg-dl-size').value,          10);
  var dlInt    = parseInt(document.getElementById('cfg-dl-interval').value,      10);

  if ([scanInt, histMin, alertThr, alertWin, latThr, dlSize, dlInt].some(isNaN)) {
    status.textContent = '✗ Valeurs invalides';
    status.style.color = 'var(--red)';
    setTimeout(function() { status.textContent = ''; }, 3000);
    return;
  }

  // URL vide → endpoint local du Pi
  var dlUrl = document.getElementById('cfg-dl-url').value.trim();
  if (!dlUrl) dlUrl = 'http://192.168.1.60:9090/api/speedtest?size_kb=' + dlSize;

  var cfg = {
    scan_interval_s:             scanInt,
    history_minutes:             histMin,
    alert_threshold_pts:         alertThr,
    alert_window:                alertWin,
    latency_alert_threshold_ms:  latThr,
    download: {
      enabled:    document.getElementById('cfg-dl-enabled').value === '1',
      url:        dlUrl,
      size_kb:    dlSize,
      interval_s: dlInt,
    }
  };
  try {
    var r = await fetch('/api/config/wifi', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(cfg)
    });
    var d = await r.json();
    if (d.ok) {
      status.textContent = '✓ Sauvegardé — appliqué immédiatement';
      status.style.color = 'var(--green)';
    } else {
      status.textContent = '✗ ' + (d.error || 'Erreur');
      status.style.color = 'var(--red)';
    }
  } catch(e) {
    status.textContent = '✗ Erreur réseau';
    status.style.color = 'var(--red)';
  }
  setTimeout(function() { status.textContent = ''; }, 4000);
}

function tab(name, el) {
  document.querySelectorAll('.tab-content').forEach(function(t){ t.classList.remove('active'); });
  document.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('active'); });
  document.getElementById('tab-' + name).classList.add('active');
  el.classList.add('active');
}

function pct(v, w, c) { return v < (w||60) ? 'var(--green)' : v < (c||85) ? 'var(--orange)' : 'var(--red)'; }

function mb(v) {
  if (!v || v < 0.001) return '0 B/s';
  return v < 1 ? (v*1024).toFixed(1)+' KB/s' : v.toFixed(2)+' MB/s';
}

function setBar(id, val, w, c) {
  var el = document.getElementById(id);
  el.style.width = val + '%';
  el.style.background = pct(val, w, c);
}

function tbody(id, html) { document.getElementById(id).innerHTML = html; }

function sparkline(values) {
  var canvas = document.getElementById('volt-canvas');
  if (!canvas || !values || values.length < 2) return;
  var ctx = canvas.getContext('2d');
  var w = canvas.offsetWidth || 600;
  canvas.width = w; canvas.height = 100;
  ctx.clearRect(0, 0, w, 100);
  var mn = Math.min.apply(null, values) - 0.02;
  var mx = Math.max.apply(null, values) + 0.02;
  var rng = mx - mn || 0.01;
  ctx.strokeStyle = '#4fc3f7'; ctx.lineWidth = 1.5; ctx.beginPath();
  values.forEach(function(v, i) {
    var x = i / (values.length-1) * w;
    var y = 94 - (v - mn) / rng * 88;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

async function svc(btn) {
  btn.disabled = true;
  await fetch('/api/service/' + btn.dataset.s + '/' + btn.dataset.a, {method:'POST'});
  btn.disabled = false;
  load();
}

async function refreshServices() {
  var btn = document.getElementById('svc-refresh-btn');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  await fetch('/api/services/refresh', {method:'POST'});
  // Attend ~3s que bg_loop() ait eu le temps de collecter
  setTimeout(function() {
    load();
    if (btn) { btn.disabled = false; btn.textContent = 'Rafraichir'; }
  }, 3000);
}

async function restartSamba() {
  var btn = document.getElementById('samba-restart-btn');
  var msg = document.getElementById('samba-restart-msg');
  btn.disabled = true;
  btn.textContent = '…';
  msg.textContent = 'Redémarrage en cours…';
  msg.style.color = 'var(--muted)';
  try {
    var r = await fetch('/api/samba/restart', { method: 'POST' });
    var data = await r.json();
    if (data.ok) {
      msg.textContent = 'Redémarré — ' + new Date().toLocaleTimeString('fr-FR');
      msg.style.color = 'var(--green)';
    } else {
      msg.textContent = 'Erreur : ' + (data.error || 'inconnue');
      msg.style.color = 'var(--red)';
    }
  } catch(e) {
    msg.textContent = 'Erreur réseau';
    msg.style.color = 'var(--red)';
  }
  btn.textContent = '↺ Relancer Samba';
  btn.disabled = false;
}

async function scanDisk() {
  var select = document.getElementById('disk-select');
  var status = document.getElementById('scan-status');
  var btn = document.getElementById('scan-btn');
  var results = document.getElementById('scan-results');
  
  var path = select.value;
  if (!path) {
    status.textContent = 'Veuillez sélectionner un disque';
    status.style.color = 'var(--red)';
    return;
  }
  
  btn.disabled = true;
  status.textContent = 'Analyse en cours...';
  status.style.color = 'var(--accent)';
  results.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px;">Analyse en cours, veuillez patienter...</div>';
  
  try {
    console.log('DEBUG: Selected path:', path);
    var t0 = Date.now();
    var scanUrl = '/api/scan?path=' + encodeURIComponent(path);
    console.log('DEBUG: Fetching:', scanUrl);
    var response = await fetch(scanUrl);
    var data = await response.json();
    console.log('DEBUG: Response data:', data);
    
    if (data.error) {
      results.innerHTML = '<div style="color:var(--red);padding:20px;">Erreur: ' + data.error + '</div>';
      status.textContent = 'Échec';
      status.style.color = 'var(--red)';
      return;
    }
    
    var elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    status.textContent = 'Analyse terminée en ' + elapsed + 's';
    status.style.color = 'var(--green)';
    
    // Display results
    if (data.length === 0) {
      results.innerHTML = '<div style="color:var(--muted);text-align:center;padding:40px;">Aucun dossier trouvé</div>';
    } else {
      var html = '<table><thead><tr><th>Dossier</th><th style="text-align:right">Taille</th><th style="width:200px">Chemin</th></tr></thead><tbody>';
      var total = 0;
      data.forEach(function(item) {
        total += item.size_mb;
        var indent = '└── '.repeat(item.depth);
        html += '<tr><td><strong>' + indent + item.name + '</strong></td>';
        html += '<td style="text-align:right;color:var(--accent);font-weight:600;">' + item.size_mb.toFixed(2) + ' MB</td>';
        html += '<td style="color:var(--muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;">' + item.path + '</td></tr>';
      });
      html += '</tbody></table>';
      html += '<div style="margin-top:15px;padding:10px;background:rgba(79,195,247,.1);border-radius:5px;color:var(--accent);">'
            + '<strong>Total analysé:</strong> ' + total.toFixed(2) + ' MB dans ' + data.length + ' dossiers'
            + '</div>';
      results.innerHTML = html;
    }
    btn.disabled = false;
  } catch (e) {
    results.innerHTML = '<div style="color:var(--red);padding:20px;">Erreur: ' + e.message + '</div>';
    status.textContent = 'Échec';
    status.style.color = 'var(--red)';
    btn.disabled = false;
  }
}
async function load() {
  var d = await fetch('/api/stats').then(function(r){ return r.json(); });
  var s = d.system || {};

  // Header
  document.getElementById('hostname').textContent = s.hostname || 'FSA-PI5';
  document.getElementById('uptime').textContent = 'Uptime: ' + (s.uptime || '—');
  document.getElementById('ts').textContent = new Date().toLocaleTimeString();
  document.getElementById('dot').style.background = 'var(--green)';

  // Header
  document.getElementById('hostname').textContent = s.hostname || 'FSA-PI5';
  document.getElementById('uptime').textContent = 'Uptime: ' + (s.uptime || '—');
  document.getElementById('ts').textContent = new Date().toLocaleTimeString();
  document.getElementById('dot').style.background = 'var(--green)';

  // CPU
  var cpu = s.cpu_percent || 0;
  document.getElementById('v-cpu').textContent = cpu.toFixed(1) + '%';
  document.getElementById('v-cpu').style.color = pct(cpu);
  // Afficher la température seulement si le monitoring est activé
  if (monitorTemperature) {
    document.getElementById('v-temp').textContent = s.cpu_temp ? s.cpu_temp.toFixed(1) + ' C' : '—';
  } else {
    document.getElementById('v-temp').textContent = '—';
  }
  setBar('b-cpu', cpu);

  // Mem
  var mem = s.mem_percent || 0;
  document.getElementById('v-mem').textContent = mem.toFixed(1) + '%';
  document.getElementById('v-mem').style.color = pct(mem);
  document.getElementById('v-mem2').textContent = ((s.mem_used_mb||0)/1024).toFixed(1) + ' / ' + ((s.mem_total_mb||0)/1024).toFixed(1) + ' GB';
  setBar('b-mem', mem);

  // Tension
  var v = d.voltage || {};
  document.getElementById('v-volt').textContent = v.volt ? v.volt.toFixed(4)+' V' : '—';
  document.getElementById('v-volt').style.color = v.critical ? 'var(--red)' : 'var(--green)';
  document.getElementById('v-volt2').textContent = v.critical ? 'SOUS-TENSION' : 'Normal';
  document.getElementById('v-volt2').style.color = v.critical ? 'var(--red)' : 'var(--muted)';

  // Réseau
  var io = d.io || {};
  document.getElementById('v-rx').textContent = mb(io.net_rx_mb);
  document.getElementById('v-tx').textContent = 'TX: ' + mb(io.net_tx_mb);

  // Alerte
  var alt = document.getElementById('volt-alert');
  if (v.critical && v.flags && v.flags.length) {
    alt.style.display = 'block';
    alt.textContent = 'Alerte: ' + v.flags.join(', ');
  } else { alt.style.display = 'none'; }

  // Disques
  var dhtml = '';
  (d.disks || []).forEach(function(k) {
    var c = pct(k.percent);
    dhtml += '<tr><td>' + k.mountpoint + '</td><td style="color:var(--muted)">' + k.fstype + '</td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:'+k.percent+'%;background:'+c+'"></div></div>'
      + '<span class="bar2-pct" style="color:'+c+'">'+k.percent+'%</span></div></td>'
      + '<td style="text-align:right;color:var(--muted)">' + k.free_gb + ' GB</td></tr>';
  });
  tbody('t-disks', dhtml || '<tr><td colspan="4" class="empty">—</td></tr>');

  // I/O
  var iohtml = '';
  [['Disque ecriture', io.disk_write_mb],['Disque lecture', io.disk_read_mb],
   ['Reseau RX', io.net_rx_mb],['Reseau TX', io.net_tx_mb]].forEach(function(r) {
    iohtml += '<tr><td>' + r[0] + '</td><td style="text-align:right;font-weight:600;color:var(--accent)">' + mb(r[1]) + '</td></tr>';
  });
  tbody('t-io', iohtml);

  // Processus
  var phtml = '';
  (d.top_cpu || []).forEach(function(p) {
    var c2 = p.cpu_percent||0, r2 = p.memory_percent||0;
    phtml += '<tr><td>' + (p.display_name||p.name||'?') + '</td><td style="text-align:right;color:var(--muted)">' + p.pid + '</td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:'+Math.min(c2,100)+'%;background:'+pct(c2,30,70)+'"></div></div>'
      + '<span class="bar2-pct" style="color:'+pct(c2,30,70)+'">'+c2.toFixed(1)+'%</span></div></td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:'+Math.min(r2,100)+'%;background:'+pct(r2)+'"></div></div>'
      + '<span class="bar2-pct">'+r2.toFixed(1)+'%</span></div></td></tr>';
  });
  tbody('t-procs', phtml || '<tr><td colspan="4" class="empty">—</td></tr>');

  // Services — heure de dernière collecte
  var svcUpEl = document.getElementById('svc-updated');
  if (svcUpEl && d.services_updated) {
    var svcDt = new Date(d.services_updated * 1000);
    svcUpEl.textContent = 'Mis à jour : ' + svcDt.toLocaleTimeString('fr-FR', {hour:'2-digit', minute:'2-digit'});
  }
  var svchtml = '';
  (d.services || []).forEach(function(k) {
    var bc = k.active==='active' ? 'ok' : (k.active==='failed' ? 'err' : 'warn');
    svchtml += '<tr><td><strong>' + k.label + '</strong></td><td style="color:var(--muted)">' + k.port + '</td>'
      + '<td><span class="badge ' + bc + '">' + k.active + '</span></td>'
      + '<td style="color:var(--muted)">' + (k.since||'—') + '</td>'
      + '<td>'
      + '<button class="btn btn-start"   data-s="'+k.service+'" data-a="start"   onclick="svc(this)">Start</button>'
      + '<button class="btn btn-restart" data-s="'+k.service+'" data-a="restart" onclick="svc(this)">Restart</button>'
      + '<button class="btn btn-stop"    data-s="'+k.service+'" data-a="stop"    onclick="svc(this)">Stop</button>'
      + '</td></tr>';
  });
  tbody('t-svc', svchtml || '<tr><td colspan="5" class="empty">—</td></tr>');

  // HTTP
  var hhtml = '';
  (d.http || []).forEach(function(k) {
    var bc = k.ok ? 'ok' : (k.status ? 'warn' : 'err');
    hhtml += '<tr><td>' + k.name + '</td>'
      + '<td><a href="' + k.url + '" target="_blank" style="color:var(--accent)">' + k.url + '</a></td>'
      + '<td><span class="badge ' + bc + '">' + (k.ok ? k.status : (k.error||'KO')) + '</span></td>'
      + '<td style="text-align:right;color:var(--muted)">' + (k.elapsed_ms||'—') + '</td></tr>';
  });
  tbody('t-http', hhtml || '<tr><td colspan="4" class="empty">—</td></tr>');

  // Tension tab
  document.getElementById('v-volt-big').textContent = v.volt ? v.volt.toFixed(4)+' V' : '—';
  document.getElementById('v-volt-big').style.color = v.critical ? 'var(--red)' : 'var(--green)';
  document.getElementById('v-volt-flags').textContent = (v.flags&&v.flags.length) ? v.flags.join(' | ') : 'Normal';
  document.getElementById('v-volt-events').textContent = (d.undervolt_events||[]).length;
  sparkline(d.voltage_history || []);

  var uvhtml = '';
  (d.undervolt_events || []).forEach(function(e) {
    uvhtml += '<tr><td style="color:var(--muted)">' + e.time + '</td>'
      + '<td style="color:var(--red);font-weight:700">' + e.volt + ' V</td>'
      + '<td>' + e.cpu + '%</td></tr>';
  });
  tbody('t-uvolt', uvhtml || '<tr><td colspan="3" class="empty">Aucun evenement</td></tr>');

  // WiFi
  var wifi   = d.wifi || {};
  var wIface = wifi.interface || {};
  var wNets  = wifi.networks  || [];
  _lastWifiNets = wNets;
  _lastAllNets  = (d.wifi || {}).all_networks || [];  // Top 10 non filtré pour la modale

  // KPI interface
  var wStateEl = document.getElementById('wifi-state');
  var wIpEl    = document.getElementById('wifi-ip');
  if (wIface.connected) {
    wStateEl.textContent = 'Connecté';
    wStateEl.style.color = 'var(--green)';
    wIpEl.textContent = wIface.connection + (wIface.ip ? ' · ' + wIface.ip : '');
  } else {
    wStateEl.textContent = wIface.state === 'unavailable' ? 'Indisponible' : 'Déconnecté';
    wStateEl.style.color = 'var(--muted)';
    wIpEl.textContent = 'wlan0 non connecté';
  }
  document.getElementById('wifi-count').textContent = _lastAllNets.length;
  var netCountEl = document.getElementById('wifi-net-count');
  if (netCountEl) netCountEl.textContent = _lastAllNets.length > 0 ? '(' + _lastAllNets.length + ')' : '';

  // KPI meilleur signal
  if (_lastAllNets.length > 0) {
    var best = _lastAllNets[0];
    document.getElementById('wifi-best-signal').textContent = best.signal + '%';
    document.getElementById('wifi-best-signal').style.color = sigColor(best.signal);
    document.getElementById('wifi-best-ssid').textContent = best.ssid;
  }

  // Synchronise l'état local avec le serveur (SSIDs surveillés)
  var wMon     = d.wifi_monitor || {};
  var monSsids = wMon.ssids || [];
  var monData  = wMon.data  || {};
  var monPing  = wMon.ping  || {};
  _monitoredSsids = new Set(monSsids);
  document.getElementById('wifi-mon-count').textContent = monSsids.length;

  // Badge d'alerte sur l'onglet WiFi (visible depuis tous les onglets)
  var hasAlert = monSsids.some(function(s) {
    var sd = monData[s] || {};
    return sd.alert || sd.latency_alert || (sd.current_signal === null && (sd.outages || []).some(function(o){ return !o.end_ts; }));
  });
  document.getElementById('wifi-alert-badge').style.display = hasAlert ? 'inline' : 'none';

  // Reconstruit les panneaux de monitoring (un par SSID surveillé)
  var panelsHtml = '';
  monSsids.forEach(function(ssid, idx) {
    var sData = monData[ssid] || {};
    panelsHtml += buildMonPanel(ssid, sData, wMon, idx);
  });
  document.getElementById('wifi-monitors').innerHTML = panelsHtml;

  // Dessine les sparklines signal + latence après injection dans le DOM
  monSsids.forEach(function(ssid, idx) {
    var sData = monData[ssid] || {};
    drawWifiSparkline(sData.history || [], 'wifi-canvas-' + idx);
    drawLatencySparkline(sData.latency_history || [], 'latency-canvas-' + idx);
  });

  // Tableau des réseaux — top 10 non filtré, bouton Surveiller / Stop par ligne
  var whtml = '';
  _lastAllNets.forEach(function(n) {
    var sc        = sigColor(n.signal);
    var qualBadge = n.signal >= 75 ? 'ok' : n.signal >= 50 ? 'warn' : 'err';
    var inUse     = n.in_use ? '<span style="color:var(--green);font-weight:700">★</span> ' : '';
    var isWatched = _monitoredSsids.has(n.ssid);
    var rowStyle  = n.in_use ? 'background:rgba(79,195,247,.06)' : (isWatched ? 'background:rgba(255,183,77,.06)' : '');
    var ssidAttr  = n.ssid.replace(/"/g, '&quot;');
    var monBtn    = isWatched
      ? '<button onclick="toggleMonitorSsid(this.dataset.ssid)" data-ssid="' + ssidAttr + '" '
        + 'style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);background:transparent;cursor:pointer;font-size:11px">Stop</button>'
      : '<button onclick="toggleMonitorSsid(this.dataset.ssid)" data-ssid="' + ssidAttr + '" '
        + 'style="padding:2px 8px;border-radius:4px;border:1px solid var(--accent);color:var(--accent);background:transparent;cursor:pointer;font-size:11px">Surveiller</button>';
    whtml += '<tr style="' + rowStyle + '">'
      + '<td>' + inUse + '</td>'
      + '<td><strong>' + n.ssid + '</strong></td>'
      + '<td style="color:var(--muted)">' + n.band + '</td>'
      + '<td style="color:var(--muted)">ch.' + n.chan + '</td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:' + n.signal + '%;background:' + sc + '"></div></div>'
      + '<span class="bar2-pct" style="color:' + sc + '">' + n.signal + '%</span></div></td>'
      + '<td><span class="badge ' + qualBadge + '">' + n.quality + '</span></td>'
      + '<td style="color:var(--muted);font-size:12px">' + n.rate + '</td>'
      + '<td style="color:var(--muted);font-size:12px">' + (n.security || 'Ouvert') + '</td>'
      + '<td>' + monBtn + '</td>'
      + '</tr>';
  });
  tbody('t-wifi', whtml || '<tr><td colspan="9" class="empty">Aucun réseau détecté</td></tr>');
  // SMB
  // Samba status
  var ss = d.samba_status || {};
  ['smbd','nmbd'].forEach(function(svc) {
    var el = document.getElementById('v-' + svc);
    if (!el) return;
    var st = ss[svc] || '—';
    el.textContent = st;
    el.style.color = st === 'active' ? 'var(--green)' : (st === 'inactive' ? 'var(--muted)' : 'var(--red)');
  });

  var smbhtml = '';
  (d.smb || []).forEach(function(k) {
    smbhtml += '<tr><td><strong>' + k.name + '</strong>'
      + (k.comment ? '<br><span style="color:var(--muted);font-size:11px">'+k.comment+'</span>' : '') + '</td>'
      + '<td style="color:var(--muted)">' + k.path + '</td>'
      + '<td><a href="' + k.url + '" style="color:var(--accent)">' + k.url + '</a></td></tr>';
  });
  tbody('t-smb', smbhtml || '<tr><td colspan="3" class="empty">—</td></tr>');

  // Watchdog Samba — journal des redémarrages
  var wdEvents = d.samba_watchdog || [];
  var wdCard   = document.getElementById('samba-watchdog-card');
  if (wdCard) wdCard.style.display = wdEvents.length ? '' : 'none';
  var wdHtml = '';
  wdEvents.slice().reverse().forEach(function(e) {
    var color = e.action === 'restarted' ? 'var(--yellow)' : 'var(--red)';
    var label = e.action === 'restarted' ? 'Redémarré' : 'Échec redémarrage';
    wdHtml += '<tr><td style="color:var(--muted)">' + e.time + '</td>'
      + '<td><strong>' + e.svc + '</strong></td>'
      + '<td style="color:' + color + '">' + label + '</td></tr>';
  });
  tbody('t-samba-watchdog', wdHtml);

  // Disk analysis - populate select
  var diskSelect = document.getElementById('disk-select');
  if (diskSelect) {
    var currentValue = diskSelect.value;
    diskSelect.innerHTML = '<option value="">Sélectionnez un disque</option>';
    (d.disks || []).forEach(function(disk) {
      var option = document.createElement('option');
      option.value = disk.mountpoint;
      option.textContent = disk.mountpoint + ' (' + disk.free_gb + ' GB libre)';
      diskSelect.appendChild(option);
    });
    if (currentValue) {
      diskSelect.value = currentValue;
    }
  }
}

// Force un scan nmcli, attend 4s puis recharge le tableau des réseaux
async function rescanWifiTable() {
  var btn    = document.getElementById('wifi-rescan-btn');
  var status = document.getElementById('wifi-rescan-status');
  btn.disabled = true;
  status.textContent = 'Scan en cours…';
  status.style.color = 'var(--accent)';
  try {
    var r = await fetch('/api/wifi/rescan', { method: 'POST' });
    var d = await r.json();
    if (!d.ok) {
      status.textContent = 'Erreur : ' + (d.error || 'inconnue');
      status.style.color = 'var(--red)';
      btn.disabled = false;
      return;
    }
    var remaining = 4;
    status.textContent = 'Mise à jour dans ' + remaining + 's…';
    var iv = setInterval(function() {
      remaining--;
      if (remaining > 0) {
        status.textContent = 'Mise à jour dans ' + remaining + 's…';
      } else {
        clearInterval(iv);
        load().then(function() {
          status.textContent = '';
          btn.disabled = false;
        });
      }
    }, 1000);
  } catch(e) {
    status.textContent = 'Erreur réseau';
    status.style.color = 'var(--red)';
    btn.disabled = false;
  }
}

load();
loadWifiConfig();
setInterval(load, 2000);
</script>


</body>
</html>
"""
