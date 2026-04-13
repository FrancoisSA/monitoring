"""
state.py — État global partagé entre le thread de collecte et les routes Flask.

Le thread bg_loop() tourne en arrière-plan et met à jour _state toutes les 2s.
Les routes Flask lisent _state via _state_lock pour éviter les accès concurrents.
"""
import collections
import threading
import time
from datetime import datetime

from config   import load_config
from system   import get_system_stats, get_disk_stats, get_top_cpu_procs, IoTracker
from services import get_services_status, get_samba_status, get_smb_shares
from network  import scan_web_processes, check_server, get_wifi_info, ping_gateway
from voltage  import get_voltage, VoltageHistory


# ── État global ────────────────────────────────────────────────────────────────

_state: dict = {
    "system":          {},
    "disks":           [],
    "io":              {},
    "services":        [],
    "http":            [],
    "voltage":         {},
    "voltage_history": [],
    "undervolt_events": [],
    "top_cpu":         [],
    "smb":             [],
    "samba_status":    {},
    "wifi":            {"interface": {}, "networks": []},
    "wifi_monitor":    {"ssid": None, "history": [], "alert": False, "ping": {}},
    "updated":         0,
}

_state_lock = threading.Lock()

# Instances partagées (initialisées une seule fois)
_io_tracker   = IoTracker()
_volt_history = VoltageHistory()

# Contrôle du monitoring de température (basculé via /api/temperature/on|off)
monitor_temperature = True

# SSID sélectionné pour le monitoring signal (None = aucun)
monitored_ssid: str | None = None

# Historique du signal pour le SSID surveillé
# Chaque entrée : {"ts": float, "time": str, "signal": int, "rate": str}
# 60 échantillons × 30s = 30 minutes de données
_wifi_signal_history: collections.deque = collections.deque(maxlen=60)


# ── Détection des chutes de signal ────────────────────────────────────────────

def _detect_signal_drop(history: list, current_signal: int, threshold: int = 20) -> bool:
    """Retourne True si le signal actuel a chuté de plus de `threshold` points
    par rapport à la moyenne des 5 derniers échantillons valides.
    """
    if len(history) < 5:
        return False
    recent_mean = sum(h["signal"] for h in history[-5:]) / 5
    return (recent_mean - current_signal) >= threshold


# ── Thread de collecte ─────────────────────────────────────────────────────────

def bg_loop():
    """Collecte toutes les métriques périodiquement et met à jour _state.

    Fréquences :
      - Système, disques, services, I/O, tension : toutes les 2s
      - WiFi scan + signal monitoring : toutes les 30s (15 × 2s)
    """
    config         = load_config()
    timeout        = config.get("timeout", 5)
    config_servers = config.get("servers", [])
    wifi_cycle     = 15  # Démarrer à 15 pour forcer la collecte WiFi au premier cycle

    while True:
        # ── Collecte principale (toutes les 2s) ──
        sys_stats    = get_system_stats(monitor_temperature)
        disks        = get_disk_stats()
        io           = _io_tracker.sample()
        services     = get_services_status()
        top_cpu      = get_top_cpu_procs(10)
        voltage      = get_voltage()
        smb          = get_smb_shares()
        samba_status = get_samba_status()

        # ── Collecte WiFi toutes les 30s ──
        wifi_cycle += 1
        if wifi_cycle >= 15:
            wifi = get_wifi_info()
            wifi_cycle = 0

            # Enregistrement du signal pour le SSID surveillé
            ssid = monitored_ssid
            wifi_mon = {"ssid": ssid, "history": list(_wifi_signal_history),
                        "alert": False, "ping": {}}
            if ssid:
                # Cherche le meilleur signal parmi toutes les entrées du SSID
                matching = [n for n in wifi["networks"] if n["ssid"] == ssid]
                if matching:
                    best = max(matching, key=lambda n: n["signal"])
                    entry = {
                        "ts":     time.time(),
                        "time":   datetime.now().strftime("%H:%M"),
                        "signal": best["signal"],
                        "rate":   best["rate"],
                    }
                    _wifi_signal_history.append(entry)
                    history = list(_wifi_signal_history)
                    alert   = _detect_signal_drop(history, best["signal"])
                    ping    = ping_gateway()
                    wifi_mon = {"ssid": ssid, "history": history,
                                "alert": alert, "ping": ping}
        else:
            with _state_lock:
                wifi     = _state.get("wifi",         {"interface": {}, "networks": []})
                wifi_mon = _state.get("wifi_monitor",  {"ssid": None, "history": [], "alert": False, "ping": {}})

        # ── Historique de tension ──
        _volt_history.add(voltage, sys_stats.get("cpu_percent", 0))

        # ── Vérifications HTTP ──
        procs = scan_web_processes()
        seen: set = set()
        server_list = []
        for s in config_servers:
            if s["url"] not in seen:
                server_list.append({"name": s["name"], "url": s["url"]})
                seen.add(s["url"])
        for p in procs:
            if p.get("port") == 9090:
                continue
            if p["url"] not in seen:
                server_list.append({"name": p["name"], "url": p["url"]})
                seen.add(p["url"])
        http_results = [check_server(s["name"], s["url"], timeout) for s in server_list]

        # ── Mise à jour thread-safe ──
        with _state_lock:
            _state["system"]           = sys_stats
            _state["disks"]            = disks
            _state["io"]               = io
            _state["services"]         = services
            _state["http"]             = http_results
            _state["voltage"]          = {
                "volt":     voltage["volt"],
                "critical": voltage["critical"],
                "flags":    voltage["flags"],
            }
            _state["voltage_history"]  = _volt_history.get_recent_volts()[-120:]
            _state["undervolt_events"] = _volt_history.get_events()
            _state["top_cpu"]          = top_cpu
            _state["smb"]              = smb
            _state["samba_status"]     = samba_status
            _state["wifi"]             = wifi
            _state["wifi_monitor"]     = wifi_mon
            _state["updated"]          = time.time()

        time.sleep(2)


def get_state() -> dict:
    """Retourne une copie thread-safe de l'état global."""
    with _state_lock:
        return dict(_state)


def set_monitored_ssid(ssid: str | None):
    """Change le SSID surveillé et remet l'historique à zéro."""
    global monitored_ssid
    monitored_ssid = ssid
    _wifi_signal_history.clear()
