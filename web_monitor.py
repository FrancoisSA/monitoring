#!/usr/bin/env python3
"""
web_monitor.py — Point d'entrée et routes Flask de Pi Monitor.
Accès : http://FSA-PI5.local:9090

Lancement :
  python web_monitor.py            # port 9090 par défaut
  python web_monitor.py --port 8888
"""

import argparse
import socket
import subprocess
import threading
from datetime import datetime

from flask import Flask, jsonify, request, Response

import state
from config    import KNOWN_SERVICES
from dashboard import HTML_DASHBOARD
from disk      import scan_directory


# ── Application Flask ──────────────────────────────────────────────────────────

app = Flask(__name__)

CODE_VERSION = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Sert le dashboard HTML principal."""
    html = HTML_DASHBOARD.replace("{{ version }}", CODE_VERSION)
    resp = Response(html, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/api/stats")
def api_stats():
    """Retourne toutes les métriques système en JSON."""
    return jsonify(state.get_state())


@app.route("/api/service/<name>/<action>", methods=["POST"])
def api_service(name: str, action: str):
    """Exécute une action systemd sur un service connu (start | stop | restart)."""
    known = {s["service"] for s in KNOWN_SERVICES}
    if name not in known:
        return jsonify({"ok": False, "error": "Service inconnu"}), 404
    if action not in ("start", "stop", "restart"):
        return jsonify({"ok": False, "error": "Action invalide"}), 400
    try:
        r = subprocess.run(
            ["sudo", "systemctl", action, name],
            capture_output=True, text=True, timeout=15,
        )
        return jsonify({"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/temperature/<toggle>", methods=["POST"])
def api_temperature(toggle: str):
    """Active ou désactive la collecte de température côté serveur (on | off)."""
    if toggle not in ("on", "off"):
        return jsonify({"ok": False, "error": "Valeur invalide, utiliser 'on' ou 'off'"}), 400
    state.monitor_temperature = (toggle == "on")
    return jsonify({"ok": True, "monitor_temperature": state.monitor_temperature})


@app.route("/api/wifi/monitor", methods=["POST"])
def api_wifi_monitor():
    """Sélectionne un SSID à surveiller (ou None pour arrêter).

    Body JSON : {"ssid": "Livebox-2A30"} ou {"ssid": null}
    """
    body = request.get_json(silent=True) or {}
    ssid = body.get("ssid") or None
    state.set_monitored_ssid(ssid)
    return jsonify({"ok": True, "monitored_ssid": ssid})


@app.route("/api/scan/<path:mountpoint>")
def api_scan(mountpoint: str):
    """Analyse les tailles de dossiers sur un point de montage."""
    if not mountpoint.startswith("/"):
        mountpoint = "/" + mountpoint
    try:
        result = scan_directory(mountpoint)
        if not result:
            return jsonify({"error": "Aucun dossier trouvé ou permissions insuffisantes"}), 403
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'analyse : {e}"}), 500


@app.route("/diag")
def diag():
    """Page de diagnostic minimale pour tester la connexion fetch/JS."""
    html = """<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Diag</title>
<style>body{background:#111;color:#eee;font-family:monospace;padding:20px}</style>
</head><body>
<h2>Diagnostic Pi Monitor</h2>
<p id="step1" style="color:orange">1. Page chargee - JS pas encore execute</p>
<p id="step2" style="color:gray">2. JS execute (attente fetch...)</p>
<p id="step3" style="color:gray">3. Fetch lance</p>
<p id="step4" style="color:gray">4. Reponse recue</p>
<pre id="result" style="color:yellow;font-size:11px"></pre>
<script>
document.getElementById('step1').style.color = 'green';
document.getElementById('step1').textContent  = '1. OK - Page chargee et JS execute';
document.getElementById('step2').style.color  = 'orange';
document.getElementById('step2').textContent  = '2. JS execute - lancement fetch...';
var url = window.location.origin + '/api/stats';
document.getElementById('step3').style.color    = 'orange';
document.getElementById('step3').textContent    = '3. Fetch lance vers ' + url;
var t0 = Date.now();
fetch(url)
  .then(function(r) {
    document.getElementById('step4').style.color   = 'orange';
    document.getElementById('step4').textContent   = '4. Reponse recue - HTTP ' + r.status + ' en ' + (Date.now()-t0) + 'ms';
    return r.json();
  })
  .then(function(d) {
    document.getElementById('step4').style.color  = 'green';
    document.getElementById('step4').textContent += ' - JSON OK';
    document.getElementById('result').textContent =
      'CPU: ' + (d.system && d.system.cpu_percent) + '%  ' +
      'RAM: ' + (d.system && d.system.mem_percent) + '%  ' +
      'Hostname: ' + (d.system && d.system.hostname);
  })
  .catch(function(e) {
    document.getElementById('step3').style.color   = 'red';
    document.getElementById('step3').textContent   = 'ERREUR: ' + e.name + ' - ' + e.message;
  });
setTimeout(function() {
  if (document.getElementById('step4').style.color === 'gray') {
    document.getElementById('step4').style.color   = 'red';
    document.getElementById('step4').textContent   = '4. TIMEOUT - pas de reponse apres 8s';
  }
}, 8000);
</script></body></html>"""
    return Response(html, mimetype="text/html")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Interface web de monitoring Pi")
    parser.add_argument("--port",  type=int, default=9090, help="Port d'écoute (défaut: 9090)")
    parser.add_argument("--host",  default="0.0.0.0",     help="Interface d'écoute (défaut: 0.0.0.0)")
    parser.add_argument("--debug", action="store_true",    help="Mode debug Flask")
    args = parser.parse_args()

    # Démarrer le thread de collecte en arrière-plan (daemon : s'arrête avec le process)
    t = threading.Thread(target=state.bg_loop, daemon=True)
    t.start()

    print(f"Pi Monitor Web — http://{socket.gethostname()}.local:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug,
            use_reloader=False, threaded=True)
