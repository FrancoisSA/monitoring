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
  <div class="tab"         onclick="tab('wifi',this)">WiFi</div>
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
    <div class="card-title">Services systemd</div>
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
  </div>
  <!-- Panneau de monitoring du SSID sélectionné -->
  <div id="wifi-mon-panel" class="card" style="display:none">
    <div class="card-title" style="display:flex;align-items:center;gap:12px">
      <span>Surveillance : <strong id="mon-ssid-name">—</strong></span>
      <button onclick="stopMonitor()" style="margin-left:auto;padding:3px 10px;border-radius:4px;border:1px solid var(--red);color:var(--red);background:transparent;cursor:pointer;font-size:12px">Arrêter</button>
    </div>
    <div id="mon-alert" style="display:none;margin-bottom:12px" class="alert">⚠ Chute de signal détectée — débit probablement dégradé</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin-bottom:16px">
      <div class="kpi">
        <div class="label">Signal actuel</div>
        <div class="value" id="mon-signal" style="font-size:24px">—</div>
        <div class="sub"   id="mon-quality">—</div>
      </div>
      <div class="kpi">
        <div class="label">Débit annoncé</div>
        <div class="value" id="mon-rate" style="font-size:20px">—</div>
      </div>
      <div class="kpi">
        <div class="label">Ping gateway</div>
        <div class="value" id="mon-ping" style="font-size:24px">—</div>
        <div class="sub"   id="mon-gw">—</div>
      </div>
      <div class="kpi">
        <div class="label">Échantillons</div>
        <div class="value" id="mon-count" style="font-size:24px">0</div>
        <div class="sub">sur 30 min max</div>
      </div>
    </div>
    <div class="card-title">Historique du signal (30 min)</div>
    <canvas id="wifi-canvas" style="height:80px"></canvas>
  </div>

  <div class="card">
    <div class="card-title">Réseaux WiFi détectés</div>
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
  </div>
  <div class="card">
    <div class="card-title">Partages Samba</div>
    <table><thead><tr><th>Partage</th><th>Chemin</th><th>URL</th></tr></thead>
    <tbody id="t-smb"></tbody></table>
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

// ── Monitoring SSID ────────────────────────────────────────────────────────────
var _monitoredSsid = null;

async function monitorSsid(ssid) {
  _monitoredSsid = ssid;
  await fetch('/api/wifi/monitor', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ssid: ssid})
  });
  document.getElementById('mon-ssid-name').textContent = ssid;
  document.getElementById('wifi-mon-panel').style.display = 'block';
}

async function stopMonitor() {
  _monitoredSsid = null;
  await fetch('/api/wifi/monitor', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ssid: null})
  });
  document.getElementById('wifi-mon-panel').style.display = 'none';
}

function drawWifiSparkline(history) {
  var canvas = document.getElementById('wifi-canvas');
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
  ctx.fillStyle = 'var(--muted, #888)'; ctx.font = '10px sans-serif';
  if (history[0])                        ctx.fillText(history[0].time,                  4, 76);
  if (history[history.length - 1])       ctx.fillText(history[history.length - 1].time, w - 32, 76);
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
    console.log('DEBUG: Fetching:', '/api/scan/' + encodeURIComponent(path));
    var response = await fetch('/api/scan/' + encodeURIComponent(path));
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
    phtml += '<tr><td>' + (p.name||'?') + '</td><td style="text-align:right;color:var(--muted)">' + p.pid + '</td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:'+Math.min(c2,100)+'%;background:'+pct(c2,30,70)+'"></div></div>'
      + '<span class="bar2-pct" style="color:'+pct(c2,30,70)+'">'+c2.toFixed(1)+'%</span></div></td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:'+Math.min(r2,100)+'%;background:'+pct(r2)+'"></div></div>'
      + '<span class="bar2-pct">'+r2.toFixed(1)+'%</span></div></td></tr>';
  });
  tbody('t-procs', phtml || '<tr><td colspan="4" class="empty">—</td></tr>');

  // Services
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
  var wifi = d.wifi || {};
  var wIface = wifi.interface || {};
  var wNets  = wifi.networks  || [];

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

  // KPI count
  document.getElementById('wifi-count').textContent = wNets.length;

  // KPI meilleur signal
  if (wNets.length > 0) {
    var best = wNets[0];
    document.getElementById('wifi-best-signal').textContent = best.signal + '%';
    document.getElementById('wifi-best-signal').style.color = best.signal >= 75 ? 'var(--green)' : best.signal >= 50 ? 'var(--orange)' : 'var(--red)';
    document.getElementById('wifi-best-ssid').textContent = best.ssid;
  }

  // Tableau réseaux
  var whtml = '';
  wNets.forEach(function(n) {
    var sigColor  = n.signal >= 75 ? 'var(--green)' : n.signal >= 50 ? 'var(--orange)' : 'var(--red)';
    var qualBadge = n.signal >= 75 ? 'ok' : n.signal >= 50 ? 'warn' : 'err';
    var inUse     = n.in_use ? '<span style="color:var(--green);font-weight:700">★</span> ' : '';
    var isWatched = (n.ssid === _monitoredSsid);
    var rowStyle  = n.in_use ? 'background:rgba(79,195,247,.06)' : (isWatched ? 'background:rgba(255,183,77,.06)' : '');
    var monBtn    = isWatched
      ? '<button onclick="stopMonitor()" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);background:transparent;cursor:pointer;font-size:11px">Stop</button>'
      : '<button onclick="monitorSsid(' + JSON.stringify(n.ssid) + ')" style="padding:2px 8px;border-radius:4px;border:1px solid var(--accent);color:var(--accent);background:transparent;cursor:pointer;font-size:11px">Surveiller</button>';
    whtml += '<tr style="' + rowStyle + '">'
      + '<td>' + inUse + '</td>'
      + '<td><strong>' + n.ssid + '</strong></td>'
      + '<td style="color:var(--muted)">' + n.band + '</td>'
      + '<td style="color:var(--muted)">ch.' + n.chan + '</td>'
      + '<td><div class="bar-wrap2"><div class="bar2"><div class="bar2-fill" style="width:' + n.signal + '%;background:' + sigColor + '"></div></div>'
      + '<span class="bar2-pct" style="color:' + sigColor + '">' + n.signal + '%</span></div></td>'
      + '<td><span class="badge ' + qualBadge + '">' + n.quality + '</span></td>'
      + '<td style="color:var(--muted);font-size:12px">' + n.rate + '</td>'
      + '<td style="color:var(--muted);font-size:12px">' + (n.security || 'Ouvert') + '</td>'
      + '<td>' + monBtn + '</td>'
      + '</tr>';
  });
  tbody('t-wifi', whtml || '<tr><td colspan="9" class="empty">Aucun réseau détecté</td></tr>');

  // Panneau de monitoring SSID
  var wMon = d.wifi_monitor || {};
  if (wMon.ssid) {
    _monitoredSsid = wMon.ssid;
    document.getElementById('wifi-mon-panel').style.display = 'block';
    document.getElementById('mon-ssid-name').textContent = wMon.ssid;

    var history = wMon.history || [];
    var last    = history.length > 0 ? history[history.length - 1] : null;

    // Signal actuel
    var monSig = document.getElementById('mon-signal');
    if (last) {
      var sc = last.signal >= 75 ? 'var(--green)' : last.signal >= 50 ? 'var(--orange)' : 'var(--red)';
      monSig.textContent = last.signal + '%';
      monSig.style.color = sc;
      document.getElementById('mon-quality').textContent =
        last.signal >= 75 ? 'Excellent' : last.signal >= 50 ? 'Bon' : last.signal >= 25 ? 'Faible' : 'Très faible';
      document.getElementById('mon-rate').textContent = last.rate || '—';
    }

    // Ping gateway
    var ping = wMon.ping || {};
    var pingEl = document.getElementById('mon-ping');
    pingEl.textContent = ping.latency_ms ? ping.latency_ms + ' ms' : '—';
    pingEl.style.color = ping.ok ? (ping.latency_ms < 20 ? 'var(--green)' : ping.latency_ms < 80 ? 'var(--orange)' : 'var(--red)') : 'var(--red)';
    document.getElementById('mon-gw').textContent = ping.ip ? 'via ' + ping.ip : 'Gateway injoignable';

    // Compteur et alerte
    document.getElementById('mon-count').textContent = history.length;
    var alertEl = document.getElementById('mon-alert');
    alertEl.style.display = wMon.alert ? 'block' : 'none';

    // Sparkline
    drawWifiSparkline(history);
  }
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

load();
setInterval(load, 2000);
</script>
</body>
</html>
"""
