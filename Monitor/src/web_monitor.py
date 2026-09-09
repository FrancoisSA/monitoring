#!/usr/bin/env python3
"""
web_monitor.py — Point d'entrée et routes Flask de Pi Monitor.
Accès : http://FSA-PI5.local:9090

Lancement :
  python web_monitor.py            # port 9090 par défaut
  python web_monitor.py --port 8888
"""

import argparse
import json
import os
import socket
import subprocess
import threading
from datetime import datetime

from flask import Flask, jsonify, request, Response

import state
from config    import KNOWN_SERVICES, CONFIG_FILE
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
def api_control_service(name, action):
    """Contrôleur pour démarrer, arrêter ou redémarrer un service système."""
    allowed_actions = ["start", "stop", "restart"]
    if action not in allowed_actions:
        return jsonify({"error": f"Action '{action}' non valide. Doit être l'un de : {', '.join(allowed_actions)}"}), 400

    # Ici, on devrait idéalement appeler une fonction dans services.py
    # qui gère la complexité SSH/sudo pour s'assurer que l'exécution est correcte.
    # Pour l'implémentation initiale, nous simulons un appel systemctl direct.
    command = f"sudo systemctl {action} {name}"

    try:
        print(f"Tentative d'exécution de la commande : {command}")
        # Exécution du processus système pour le contrôle
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, check=True
        )
        return jsonify({
            "status": "success",
            "message": f"Service '{name}' {action} réussi.",
            "output": result.stdout
        })

    except subprocess.CalledProcessError as e:
        error_msg = f"Erreur lors du contrôle du service '{name}' : {e.stderr}"
        return jsonify({"status": "error", "message": error_msg, "details": e.output}), 500
    except Exception as e:
        return jsonify({"status": "fatal_error", "message": f"Une erreur imprévue est survenue : {str(e)}"}), 500


@app.route("/api/temperature/<toggle>", methods=["POST"])
def api_temperature(toggle: str):
    """Active ou désactive la collecte de température côté serveur (on | off)."""
    if toggle not in ("on", "off"):
        return jsonify({"ok": False, "error": "Valeur invalide, utiliser 'on' ou 'off'"}), 400
    state.monitor_temperature = (toggle == "on")
    return jsonify({"ok": True, "monitor_temperature": state.monitor_temperature})


@app.route("/api/config")
def api_config_get():
    """Retourne la configuration complète (config.json)."""
    try:
        with open(CONFIG_FILE) as f:
            return jsonify(json.load(f))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config/wifi", methods=["POST"])
def api_config_wifi():
    """Met à jour les paramètres WiFi, persiste dans config.json et les applique à chaud.

    Body JSON : {"scan_interval_s": 30, "history_minutes": 30,
                 "alert_threshold_pts": 20, "alert_window": 5}
    """
    body = request.get_json(silent=True) or {}

    # Validation des paramètres principaux
    rules = {
        "scan_interval_s":     (int, 5,   3600),
        "history_minutes":     (int, 1,   1440),
        "alert_threshold_pts": (int, 1,   100),
        "alert_window":        (int, 2,   60),
    }
    wcfg = {}
    for key, (typ, lo, hi) in rules.items():
        if key in body:
            try:
                val = typ(body[key])
                if not (lo <= val <= hi):
                    return jsonify({"ok": False, "error": f"{key} hors bornes ({lo}–{hi})"}), 400
                wcfg[key] = val
            except (ValueError, TypeError):
                return jsonify({"ok": False, "error": f"{key} invalide"}), 400

    # Validation de la section download (optionnelle)
    if "download" in body:
        dl_body = body["download"]
        dl_rules = {
            "size_kb":    (int,  64, 10240),
            "interval_s": (int,  30, 86400),
        }
        dl = {}
        if "enabled" in dl_body:
            dl["enabled"] = bool(dl_body["enabled"])
        if "url" in dl_body:
            dl["url"] = str(dl_body["url"])[:500]
        for key, (typ, lo, hi) in dl_rules.items():
            if key in dl_body:
                try:
                    val = typ(dl_body[key])
                    if not (lo <= val <= hi):
                        return jsonify({"ok": False, "error": f"download.{key} hors bornes ({lo}–{hi})"}), 400
                    dl[key] = val
                except (ValueError, TypeError):
                    return jsonify({"ok": False, "error": f"download.{key} invalide"}), 400
        wcfg["download"] = dl

    # Lecture, fusion et écriture de config.json
    try:
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        cfg["wifi"] = {**cfg.get("wifi", {}), **wcfg}
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        return jsonify({"ok": False, "error": f"Écriture config : {e}"}), 500

    # Application immédiate sans redémarrage
    state.reload_wifi_config(cfg["wifi"])
    return jsonify({"ok": True, "wifi": cfg["wifi"]})


@app.route("/api/services/refresh", methods=["POST"])
def api_services_refresh():
    """Déclenche une collecte immédiate des services systemd (au prochain cycle bg_loop, ~2s)."""
    state.force_services_refresh()
    return jsonify({"ok": True})


@app.route("/api/samba/restart", methods=["POST"])
def api_samba_restart():
    """Redémarre smbd et nmbd immédiatement via systemctl."""
    results = []
    for svc in ("smbd", "nmbd"):
        try:
            r = subprocess.run(
                ["/usr/bin/sudo", "/usr/bin/systemctl", "restart", svc],
                capture_output=True, text=True, timeout=15,
            )
            results.append({"svc": svc, "ok": r.returncode == 0, "stderr": r.stderr.strip()})
        except Exception as e:
            results.append({"svc": svc, "ok": False, "stderr": str(e)})
    all_ok = all(r["ok"] for r in results)
    # Force une mise à jour de l'état Samba dans le prochain cycle
    state.force_services_refresh()
    return jsonify({"ok": all_ok, "results": results,
                    "error": "; ".join(r["stderr"] for r in results if not r["ok"]) or None})


@app.route("/api/wifi/rescan", methods=["POST"])
def api_wifi_rescan():
    """Force un scan WiFi actif via nmcli."""
    try:
        subprocess.run(
            ["/usr/bin/sudo", "/usr/bin/nmcli", "dev", "wifi", "rescan"],
            capture_output=True, text=True, timeout=10
        )
        return jsonify({"ok": True})
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Timeout nmcli rescan"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/wifi/monitor", methods=["POST"])
def api_wifi_monitor():
    """Ajoute ou supprime un SSID de la liste de surveillance.

    Body JSON : {"ssid": "Livebox-2A30", "watch": true}  → démarre la surveillance
                {"ssid": "Livebox-2A30", "watch": false} → arrête la surveillance
    """
    body = request.get_json(silent=True) or {}
    ssid = body.get("ssid")
    if not ssid:
        return jsonify({"ok": False, "error": "ssid requis"}), 400
    watch = bool(body.get("watch", True))
    state.toggle_monitored_ssid(ssid, watch)
    return jsonify({"ok": True, "monitored_ssids": list(state.monitored_ssids)})


@app.route("/api/scan")
def api_scan():
    """Analyse les tailles de dossiers sur un point de montage.
    Paramètre GET : path (ex: /home ou /)
    """
    mountpoint = request.args.get("path", "").strip()
    if not mountpoint:
        return jsonify({"error": "Paramètre 'path' manquant"}), 400
    if not mountpoint.startswith("/"):
        mountpoint = "/" + mountpoint
    try:
        result = scan_directory(mountpoint)
        if not result:
            return jsonify({"error": "Aucun dossier trouvé ou permissions insuffisantes"}), 403
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Erreur lors de l'analyse : {e}"}), 500


@app.route("/api/speedtest")
def api_speedtest():
    """Sert des données aléatoires pour les tests de débit WiFi.
    Paramètre GET : size_kb (défaut 1024, max 10240).
    Usage : configurer l'URL de test sur http://<eth0-ip>:9090/api/speedtest
    Le trafic passe alors par wlan0 → AP → eth0, mesurant le vrai débit WiFi.
    """
    try:
        size_kb = min(max(1, int(request.args.get("size_kb", 1024))), 10240)
    except (ValueError, TypeError):
        size_kb = 1024
    data = os.urandom(size_kb * 1024)
    resp = Response(data, mimetype="application/octet-stream")
    resp.headers["Cache-Control"] = "no-store"
    return resp


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
