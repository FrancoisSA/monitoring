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
from services import get_services_status, get_samba_status, get_smb_shares, watchdog_samba
from network  import scan_web_processes, check_server, get_wifi_info, ping_gateway, measure_download
from voltage  import get_voltage, VoltageHistory


# ── État global ────────────────────────────────────────────────────────────────

_state: dict = {
    "system":              {},
    "disks":               [],
    "io":                  {},
    "services":            [],
    "services_updated":    0,
    "http":                [],
    "voltage":             {},
    "voltage_history":     [],
    "undervolt_events":    [],
    "top_cpu":             [],
    "smb":                 [],
    "samba_status":        {},
    "samba_watchdog":      [],   # journal des redémarrages automatiques (max 50)
    "wifi":             {"interface": {}, "networks": []},
    # Structure wifi_monitor :
    # {
    #   "ssids": ["SSID1", "SSID2"],          liste des SSIDs surveillés
    #   "data":  {                             données par SSID
    #     "SSID1": {
    #       "history":        [...],           60 échantillons max × 30s = 30 min
    #       "alert":          bool,            chute de signal détectée
    #       "outages":        [...],           journal des coupures (20 dernières)
    #       "current_signal": int | None,      signal courant (None = SSID invisible)
    #       "current_rate":   str | None,      débit annoncé (ex: "270 Mbit/s")
    #     },
    #     ...
    #   },
    #   "ping": {...}                          ping gateway commun (Pi est sur eth0)
    # }
    "wifi_monitor":    {"ssids": [], "data": {}, "ping": {}},
    "updated":         0,
}

_state_lock = threading.Lock()

# Instances partagées (initialisées une seule fois)
_io_tracker   = IoTracker()
_volt_history = VoltageHistory()

# Contrôle du monitoring de température (basculé via /api/temperature/on|off)
monitor_temperature = True

# SSIDs sélectionnés pour le monitoring signal (ensemble, plusieurs simultanément)
monitored_ssids: set = set()

# Historique du signal par SSID surveillé
# {ssid: deque(maxlen=N)} — chaque entrée : {"ts": float, "time": str, "signal": int, "rate": str}
_wifi_histories: dict = {}

# Journal des coupures par SSID
# {ssid: [{"start_ts": float, "start_time": str, "end_ts": float|None,
#           "end_time": str|None, "duration_s": int|None}]}
_wifi_outages: dict = {}

# État courant : le SSID est-il actuellement en coupure (absent du scan) ?
_wifi_in_outage: dict = {}

# Journal des alertes de chute de signal par SSID (max 50 par SSID)
# Chaque entrée : {"ts": float, "time": str, "signal": int,
#                  "avg_signal": float, "drop_pts": float}
_wifi_alert_events: dict = {}

# État courant : le SSID est-il en alerte (pour détecter la transition False→True) ?
_wifi_in_alert: dict = {}

# Paramètres WiFi — initialisés depuis config.json au démarrage de bg_loop(),
# puis mis à jour à chaud via reload_wifi_config() sans redémarrer le service.
# (valeurs par défaut utilisées si toggle_monitored_ssid() est appelé avant bg_loop)
_wifi_scan_interval_s:     int = 30   # secondes entre deux scans nmcli
_wifi_history_maxlen:      int = 60   # nombre max d'échantillons conservés
_wifi_alert_threshold_pts: int = 20   # chute de signal (pts) déclenchant l'alerte
_wifi_alert_window:        int = 5    # nombre d'échantillons pour la moyenne glissante
_wifi_tick:                int = 15   # cycles de 2s entre deux scans (= scan_interval_s // 2)

# Ping WiFi
_wifi_ping_iface: str = "wlan0"       # interface utilisée pour le ping de latence

# Test de téléchargement (optionnel)
_wifi_dl_enabled:  bool = False       # activé/désactivé
_wifi_dl_url:      str  = ""          # URL à télécharger
_wifi_dl_size_kb:  int  = 1024        # taille à télécharger (Ko)
_wifi_dl_tick:     int  = 150         # cycles de 2s entre deux tests (= interval_s // 2)

# Historiques supplémentaires par SSID
_wifi_latency_histories:  dict = {}   # {ssid: deque} — latence wlan0 en ms
_wifi_download_histories: dict = {}   # {ssid: deque} — débit en MB/s

# Alertes latence par SSID
_wifi_latency_alert_threshold_ms: int = 100  # Seuil au-dessus duquel on déclenche une alerte
_wifi_latency_alert_events: dict = {}        # {ssid: [...]} — journal des alertes latence (max 50)
_wifi_latency_in_alert: dict = {}            # {ssid: bool} — état d'alerte courant (pour détecter la transition)

# Cycle pour le test de téléchargement (indépendant du cycle WiFi)
_wifi_dl_cycle: int = 0

# Cycle pour les services systemd (toutes les 5 minutes = 150 × 2s)
_services_tick:  int = 150
_services_cycle: int = 150  # déclenche la collecte dès le premier cycle

# Watchdog Samba (toutes les 6 heures = 10 800 × 2s)
_samba_watchdog_tick:  int = 10800
_samba_watchdog_cycle: int = 0    # ne se déclenche pas au premier démarrage
_samba_watchdog_events: list = []  # journal des actions (max 50)


# ── Détection des chutes de signal ────────────────────────────────────────────

def _detect_signal_drop(history: list, current_signal: int):
    """Détecte une chute de signal par rapport à la moyenne glissante.

    Retourne (alert: bool, avg_signal: float, drop_pts: float).
    alert=True si la chute dépasse _wifi_alert_threshold_pts.
    """
    window = _wifi_alert_window
    if len(history) < window:
        return False, 0.0, 0.0
    avg = sum(h["signal"] for h in history[-window:]) / window
    drop = avg - current_signal
    return drop >= _wifi_alert_threshold_pts, round(avg, 1), round(drop, 1)


def _ensure_ssid_state(ssid: str):
    """Initialise les structures de données pour un SSID si elles n'existent pas encore.
    Utilise _wifi_history_maxlen pour dimensionner les deques.
    """
    if ssid not in _wifi_histories:
        _wifi_histories[ssid] = collections.deque(maxlen=_wifi_history_maxlen)
    if ssid not in _wifi_outages:
        _wifi_outages[ssid] = []
    if ssid not in _wifi_in_outage:
        _wifi_in_outage[ssid] = False
    if ssid not in _wifi_latency_histories:
        _wifi_latency_histories[ssid] = collections.deque(maxlen=_wifi_history_maxlen)
    if ssid not in _wifi_download_histories:
        _wifi_download_histories[ssid] = collections.deque(maxlen=_wifi_history_maxlen)
    if ssid not in _wifi_alert_events:
        _wifi_alert_events[ssid] = []
    if ssid not in _wifi_in_alert:
        _wifi_in_alert[ssid] = False
    if ssid not in _wifi_latency_alert_events:
        _wifi_latency_alert_events[ssid] = []
    if ssid not in _wifi_latency_in_alert:
        _wifi_latency_in_alert[ssid] = False


# ── Thread de collecte ─────────────────────────────────────────────────────────

def bg_loop():
    """Collecte toutes les métriques périodiquement et met à jour _state.

    Fréquences :
      - Système, disques, I/O, tension : toutes les 2s
      - Services systemd + Samba      : toutes les 5 min (150 × 2s)
      - WiFi scan + signal monitoring : toutes les 30s (15 × 2s)
    """
    global _wifi_scan_interval_s, _wifi_history_maxlen
    global _wifi_alert_threshold_pts, _wifi_alert_window, _wifi_tick
    global _wifi_dl_cycle
    global _services_cycle
    global _samba_watchdog_cycle, _samba_watchdog_events

    config         = load_config()
    timeout        = config.get("timeout", 5)
    config_servers = config.get("servers", [])

    # ── Paramètres WiFi depuis config.json ──
    reload_wifi_config(config.get("wifi", {}))

    wifi_cycle    = _wifi_tick   # Déclencher dès le premier cycle WiFi
    _wifi_dl_cycle = _wifi_dl_tick  # Déclencher le premier test de téléchargement immédiatement

    # Initialise les SSIDs surveillés depuis la config (démarrage automatique)
    for ssid in config.get("wifi_ssids", []):
        toggle_monitored_ssid(ssid, True)

    while True:
        # ── Collecte principale (toutes les 2s) ──
        sys_stats = get_system_stats(monitor_temperature)
        disks     = get_disk_stats()
        io        = _io_tracker.sample()
        top_cpu   = get_top_cpu_procs(10)
        voltage   = get_voltage()

        # ── Services systemd + Samba (toutes les 5 minutes) ──
        _services_cycle += 1
        if _services_cycle >= _services_tick:
            services      = get_services_status()
            smb           = get_smb_shares()
            samba_status  = get_samba_status()
            _services_cycle = 0
            services_ts   = time.time()
        else:
            with _state_lock:
                services     = _state["services"]
                smb          = _state["smb"]
                samba_status = _state["samba_status"]
                services_ts  = _state.get("services_updated", 0)

        # ── Watchdog Samba (toutes les 6 heures) ──
        _samba_watchdog_cycle += 1
        if _samba_watchdog_cycle >= _samba_watchdog_tick:
            _samba_watchdog_cycle = 0
            new_events = watchdog_samba()
            # Ne conserve que les redémarrages et échecs (pas les "ok") dans le journal
            _samba_watchdog_events.extend(e for e in new_events if e["action"] != "ok")
            if len(_samba_watchdog_events) > 50:
                _samba_watchdog_events = _samba_watchdog_events[-50:]
            # Met à jour samba_status après une éventuelle action
            samba_status = get_samba_status()

        # ── Collecte WiFi toutes les 30s ──
        wifi_cycle += 1
        if wifi_cycle >= _wifi_tick:  # _wifi_tick est mis à jour à chaud par reload_wifi_config()
            wifi_raw  = get_wifi_info()
            wifi_cycle = 0

            # Top 10 SSIDs uniques par signal (avant filtre) — exposés à la modale de surveillance
            _seen_top, wifi_top10 = set(), []
            for _n in sorted(wifi_raw["networks"], key=lambda n: -n["signal"]):
                if _n["ssid"] not in _seen_top:
                    _seen_top.add(_n["ssid"])
                    wifi_top10.append(_n)
                if len(wifi_top10) >= 10:
                    break

            # Filtre le tableau des réseaux aux seuls SSIDs configurés
            allowed = set(config.get("wifi_ssids", []))
            if allowed:
                wifi_raw["networks"] = [n for n in wifi_raw["networks"] if n["ssid"] in allowed]
            wifi = wifi_raw
            wifi["all_networks"] = wifi_top10  # Top 10 non filtré pour la modale

            # Copie thread-safe de l'ensemble des SSIDs surveillés
            ssids = set(monitored_ssids)
            now_str = datetime.now().strftime("%H:%M")

            wifi_mon_data = {}

            for ssid in ssids:
                _ensure_ssid_state(ssid)

                # Cherche le meilleur signal parmi toutes les entrées du SSID dans le scan
                matching = [n for n in wifi["networks"] if n["ssid"] == ssid]

                if matching:
                    # SSID visible — enregistre le signal
                    best = max(matching, key=lambda n: n["signal"])
                    entry = {
                        "ts":     time.time(),
                        "time":   now_str,
                        "signal": best["signal"],
                        "rate":   best["rate"],
                    }
                    _wifi_histories[ssid].append(entry)

                    # Fin de coupure si on était hors-ligne
                    if _wifi_in_outage[ssid]:
                        _wifi_in_outage[ssid] = False
                        _wifi_in_alert[ssid]  = False  # reset alerte après coupure
                        outages = _wifi_outages[ssid]
                        if outages and outages[-1]["end_ts"] is None:
                            end_ts = time.time()
                            outages[-1]["end_ts"]    = end_ts
                            outages[-1]["end_time"]  = now_str
                            outages[-1]["duration_s"] = int(end_ts - outages[-1]["start_ts"])

                    history = list(_wifi_histories[ssid])
                    alert, avg_sig, drop_pts = _detect_signal_drop(history, best["signal"])

                    # Log de l'alerte uniquement à la transition False → True
                    if alert and not _wifi_in_alert[ssid]:
                        _wifi_alert_events[ssid].append({
                            "ts":         time.time(),
                            "time":       now_str,
                            "signal":     best["signal"],
                            "avg_signal": avg_sig,
                            "drop_pts":   drop_pts,
                        })
                        # Limite à 50 événements
                        if len(_wifi_alert_events[ssid]) > 50:
                            _wifi_alert_events[ssid] = _wifi_alert_events[ssid][-50:]
                    _wifi_in_alert[ssid] = alert

                    wifi_mon_data[ssid] = {
                        "history":        history,
                        "alert":          alert,
                        "outages":        list(_wifi_outages[ssid])[-20:],
                        "alert_events":   list(_wifi_alert_events[ssid])[-20:],
                        "current_signal": best["signal"],
                        "current_rate":   best["rate"],
                    }

                else:
                    # SSID non visible → début de coupure si ce n'est pas déjà le cas
                    if not _wifi_in_outage[ssid]:
                        _wifi_in_outage[ssid] = True
                        _wifi_outages[ssid].append({
                            "start_ts":   time.time(),
                            "start_time": now_str,
                            "end_ts":     None,
                            "end_time":   None,
                            "duration_s": None,
                        })

                    wifi_mon_data[ssid] = {
                        "history":        list(_wifi_histories[ssid]),
                        "alert":          False,
                        "outages":        list(_wifi_outages[ssid])[-20:],
                        "alert_events":   list(_wifi_alert_events[ssid])[-20:],
                        "current_signal": None,
                        "current_rate":   None,
                    }

            # Ping gateway via eth0 (référence filaire) et via wlan0 (latence WiFi réelle)
            ping_eth0  = ping_gateway()                       if ssids else {}
            ping_wlan0 = ping_gateway(iface=_wifi_ping_iface) if ssids else {}

            # Enregistre la latence wlan0 dans l'historique de chaque SSID surveillé
            for ssid in ssids:
                lat = ping_wlan0.get("latency_ms")
                if lat is not None:
                    _wifi_latency_histories[ssid].append({
                        "ts": time.time(), "time": now_str, "latency_ms": lat
                    })
                    # Détection d'alerte latence — log uniquement à la transition normale → dépassement
                    lat_alert = lat > _wifi_latency_alert_threshold_ms
                    if lat_alert and not _wifi_latency_in_alert.get(ssid, False):
                        _wifi_latency_alert_events[ssid].append({
                            "ts":         time.time(),
                            "time":       now_str,
                            "latency_ms": lat,
                        })
                        if len(_wifi_latency_alert_events[ssid]) > 50:
                            _wifi_latency_alert_events[ssid] = _wifi_latency_alert_events[ssid][-50:]
                    _wifi_latency_in_alert[ssid] = lat_alert
                else:
                    _wifi_latency_in_alert[ssid] = False

            # Test de téléchargement (cycle indépendant, optionnel)
            _wifi_dl_cycle += 1
            download_result = None
            if _wifi_dl_enabled and _wifi_dl_url and _wifi_dl_cycle >= _wifi_dl_tick:
                _wifi_dl_cycle = 0
                download_result = measure_download(_wifi_dl_url, _wifi_dl_size_kb, _wifi_ping_iface)
                download_result["time"] = now_str
                # Enregistre dans l'historique de chaque SSID surveillé
                if download_result["ok"]:
                    for ssid in ssids:
                        _wifi_download_histories[ssid].append({
                            "ts": time.time(), "time": now_str,
                            "speed_mbps": download_result["speed_mbps"]
                        })

            # Enrichit chaque SSID avec latence + download
            for ssid in ssids:
                if ssid in wifi_mon_data:
                    wifi_mon_data[ssid]["latency_ms"]           = ping_wlan0.get("latency_ms")
                    wifi_mon_data[ssid]["latency_history"]      = list(_wifi_latency_histories[ssid])
                    wifi_mon_data[ssid]["latency_alert"]        = _wifi_latency_in_alert.get(ssid, False)
                    wifi_mon_data[ssid]["latency_alert_events"] = list(_wifi_latency_alert_events.get(ssid, []))[-20:]
                    wifi_mon_data[ssid]["download"]             = download_result
                    wifi_mon_data[ssid]["download_history"]     = list(_wifi_download_histories[ssid])

            wifi_mon = {
                "ssids":            list(ssids),
                "data":             wifi_mon_data,
                "ping":             ping_eth0,
                "ping_wlan0":       ping_wlan0,
                "download_enabled": _wifi_dl_enabled,
            }

        else:
            with _state_lock:
                wifi     = _state.get("wifi",        {"interface": {}, "networks": []})
                wifi_mon = dict(_state.get("wifi_monitor", {"ssids": [], "data": {}, "ping": {}}))
            # Toujours refléter la liste courante des SSIDs surveillés,
            # même entre les cycles WiFi, pour que l'UI reflète le clic immédiatement
            wifi_mon["ssids"] = list(monitored_ssids)

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
            _state["system"]            = sys_stats
            _state["disks"]             = disks
            _state["io"]                = io
            _state["services"]          = services
            _state["services_updated"]  = services_ts
            _state["http"]              = http_results
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
            _state["samba_watchdog"]   = list(_samba_watchdog_events)
            _state["wifi"]             = wifi
            _state["wifi_monitor"]     = wifi_mon
            _state["updated"]          = time.time()

        time.sleep(2)


def get_state() -> dict:
    """Retourne une copie thread-safe de l'état global."""
    with _state_lock:
        return dict(_state)


def reload_wifi_config(wcfg: dict):
    """Met à jour les paramètres WiFi à chaud (sans redémarrer le service).

    Appelé au démarrage depuis bg_loop() et via POST /api/config/wifi.
    Recrée les deques si la taille de l'historique change.
    """
    global _wifi_scan_interval_s, _wifi_history_maxlen
    global _wifi_alert_threshold_pts, _wifi_alert_window, _wifi_tick
    global _wifi_ping_iface
    global _wifi_dl_enabled, _wifi_dl_url, _wifi_dl_size_kb, _wifi_dl_tick
    global _wifi_latency_alert_threshold_ms

    _wifi_scan_interval_s     = max(5,  wcfg.get("scan_interval_s",     30))
    _wifi_alert_threshold_pts = max(1,  wcfg.get("alert_threshold_pts", 20))
    _wifi_alert_window        = max(2,  wcfg.get("alert_window",         5))
    history_minutes           = max(1,  wcfg.get("history_minutes",     30))
    new_maxlen                = max(10, (history_minutes * 60) // _wifi_scan_interval_s)
    _wifi_tick                = max(1,  _wifi_scan_interval_s // 2)
    _wifi_ping_iface                 = wcfg.get("ping_iface", "wlan0") or "wlan0"
    _wifi_latency_alert_threshold_ms = max(5, wcfg.get("latency_alert_threshold_ms", 100))

    # Paramètres du test de téléchargement
    dl = wcfg.get("download", {})
    _wifi_dl_enabled  = bool(dl.get("enabled", False))
    _wifi_dl_url      = str(dl.get("url", ""))
    _wifi_dl_size_kb  = max(64, min(int(dl.get("size_kb", 1024)), 10240))
    dl_interval_s     = max(30, int(dl.get("interval_s", 300)))
    _wifi_dl_tick     = max(1, dl_interval_s // 2)

    # Recrée les deques si le maxlen change (préserve les données existantes)
    if new_maxlen != _wifi_history_maxlen:
        _wifi_history_maxlen = new_maxlen
        for histories in (_wifi_histories, _wifi_latency_histories, _wifi_download_histories):
            for ssid in list(histories.keys()):
                old_data = list(histories[ssid])
                histories[ssid] = collections.deque(old_data[-new_maxlen:], maxlen=new_maxlen)


def force_services_refresh():
    """Force la collecte des services au prochain cycle bg_loop (dans ~2s)."""
    global _services_cycle
    _services_cycle = _services_tick


def toggle_monitored_ssid(ssid: str, watch: bool):
    """Ajoute ou supprime un SSID de l'ensemble surveillé.

    watch=True  → démarre la surveillance (initialise les structures si besoin)
    watch=False → arrête la surveillance (conserve l'historique et les coupures)
    """
    global monitored_ssids
    if watch:
        monitored_ssids.add(ssid)
        _ensure_ssid_state(ssid)
    else:
        monitored_ssids.discard(ssid)
