"""
network.py — Vérification des serveurs HTTP, détection des processus web et monitoring WiFi.
"""
import subprocess
import time

import psutil
import requests as req_lib

from config import WEB_NAMES, WEB_PORTS

# Chemin absolu de nmcli (le service systemd a un PATH limité)
NMCLI = "/usr/bin/nmcli"


# ── Détection des processus web en écoute ─────────────────────────────────────

def scan_web_processes() -> list:
    """Détecte les serveurs web actifs en scannant les ports TCP en écoute."""
    found: dict = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != "LISTEN" or not conn.pid:
                continue
            port = conn.laddr.port
            if port in found:
                continue
            try:
                proc = psutil.Process(conn.pid)
                name = proc.name()
                if not (any(w in name.lower() for w in WEB_NAMES) or port in WEB_PORTS):
                    continue
                scheme = "https" if port == 443 else "http"
                url = (f"{scheme}://localhost" if port in (80, 443)
                       else f"{scheme}://localhost:{port}")
                found[port] = {"name": name, "pid": conn.pid, "port": port, "url": url}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except psutil.AccessDenied:
        pass
    return list(found.values())


# ── Vérification HTTP ──────────────────────────────────────────────────────────

def check_server(name: str, url: str, timeout: int = 5) -> dict:
    """Vérifie la disponibilité d'un serveur HTTP et mesure sa latence."""
    t0 = time.time()
    try:
        resp = req_lib.get(url, timeout=timeout, allow_redirects=True)
        ms   = (time.time() - t0) * 1000
        return {"name": name, "url": url, "status": resp.status_code,
                "elapsed_ms": round(ms, 1), "ok": resp.status_code < 400, "error": None}
    except req_lib.exceptions.ConnectionError:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": "Connexion refusée"}
    except req_lib.exceptions.Timeout:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": f"Timeout >{timeout}s"}
    except Exception as e:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": str(e)[:50]}


# ── Ping vers la passerelle par défaut ────────────────────────────────────────

def _get_default_gateway():
    """Retourne l'IP de la passerelle par défaut via 'ip route show default'."""
    try:
        out = subprocess.check_output(
            ["/usr/bin/ip", "route", "show", "default"], text=True, timeout=3
        )
        for line in out.splitlines():
            parts = line.split()
            if "via" in parts:
                return parts[parts.index("via") + 1]
    except Exception:
        pass
    return None


def ping_gateway(iface: str = None) -> dict:
    """Ping la passerelle par défaut et retourne la latence en ms.

    iface : si fourni (ex: 'wlan0'), force le ping sur cette interface.
    Retourne {"ip": str, "iface": str|None, "latency_ms": float|None, "ok": bool}.
    """
    import re
    gateway = _get_default_gateway()
    if not gateway:
        return {"ip": None, "iface": iface, "latency_ms": None, "ok": False}

    try:
        cmd = ["/usr/bin/ping", "-c", "2", "-W", "2"]
        if iface:
            cmd += ["-I", iface]
        cmd.append(gateway)
        out = subprocess.check_output(cmd, text=True, timeout=8, stderr=subprocess.DEVNULL)
        m = re.search(r"rtt min/avg/max/mdev = [\d.]+/([\d.]+)/", out)
        latency = round(float(m.group(1)), 1) if m else None
        return {"ip": gateway, "iface": iface, "latency_ms": latency, "ok": latency is not None}
    except Exception:
        return {"ip": gateway, "iface": iface, "latency_ms": None, "ok": False}


def measure_download(url: str, size_kb: int = 1024, iface: str = "wlan0") -> dict:
    """Mesure le débit de téléchargement réel en MB/s via curl.

    Force l'interface réseau spécifiée (ex: wlan0) pour mesurer le débit WiFi réel.
    Retourne {"speed_mbps": float|None, "elapsed_s": float, "ok": bool, "error": str|None}.
    """
    try:
        cmd = [
            "/usr/bin/curl", "-s", "-o", "/dev/null",
            "--interface", iface,
            "--max-time", "20",
            "-w", "%{speed_download} %{time_total}",
            url,
        ]
        out = subprocess.check_output(cmd, text=True, timeout=25, stderr=subprocess.DEVNULL)
        parts = out.strip().split()
        if len(parts) >= 2:
            speed_bps  = float(parts[0])
            elapsed    = round(float(parts[1]), 2)
            speed_mbps = round(speed_bps / (1024 * 1024), 2)
            return {"speed_mbps": speed_mbps, "elapsed_s": elapsed,
                    "ok": speed_mbps > 0, "error": None}
        return {"speed_mbps": None, "elapsed_s": 0, "ok": False, "error": "Format inattendu"}
    except subprocess.TimeoutExpired:
        return {"speed_mbps": None, "elapsed_s": 20, "ok": False, "error": "Timeout"}
    except Exception as e:
        return {"speed_mbps": None, "elapsed_s": 0, "ok": False, "error": str(e)[:60]}


# ── Monitoring WiFi ────────────────────────────────────────────────────────────

def get_wifi_info() -> dict:
    """Collecte l'état de wlan0 et la liste des réseaux WiFi visibles via nmcli.

    Retourne :
      - interface : état de wlan0 (connecté, déconnecté, indisponible)
      - networks  : liste des réseaux triés par signal décroissant
    """
    result = {"interface": {"state": "unknown", "connected": False}, "networks": []}

    # ── État de l'interface wlan0 ──
    try:
        out = subprocess.check_output(
            [NMCLI, "-t", "-f", "GENERAL.STATE,GENERAL.CONNECTION,IP4.ADDRESS",
             "device", "show", "wlan0"],
            text=True, timeout=5, stderr=subprocess.DEVNULL
        )
        state_line = next((l for l in out.splitlines() if "GENERAL.STATE" in l), "")
        conn_line  = next((l for l in out.splitlines() if "GENERAL.CONNECTION" in l), "")
        ip_line    = next((l for l in out.splitlines() if "IP4.ADDRESS" in l), "")

        connected = ":100" in state_line  # code 100 = activé dans nmcli
        result["interface"] = {
            "state":      "connected" if connected else "disconnected",
            "connected":  connected,
            "connection": conn_line.split(":", 1)[-1].strip() if conn_line else "",
            "ip":         ip_line.split(":", 1)[-1].strip()  if ip_line  else "",
        }
    except Exception:
        result["interface"] = {"state": "unavailable", "connected": False,
                               "connection": "", "ip": ""}

    # ── Scan des réseaux WiFi (cache NetworkManager, mis à jour passivement) ──
    try:
        out = subprocess.check_output(
            [NMCLI, "-t", "-f",
             "IN-USE,SSID,BSSID,CHAN,FREQ,RATE,SIGNAL,SECURITY",
             "dev", "wifi", "list"],
            text=True, timeout=10, stderr=subprocess.DEVNULL
        )
        networks   = []
        seen_bssid = set()

        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) < 13:
                continue

            # nmcli échappe les ':' du BSSID avec '\:' → parts[2..7]
            in_use = parts[0].strip() == "*"
            ssid   = parts[1].strip() or "<caché>"
            bssid  = ":".join(p.lstrip("\\") for p in parts[2:8])
            rest   = parts[8:]

            if len(rest) < 4 or bssid in seen_bssid:
                continue
            seen_bssid.add(bssid)

            chan     = rest[0].strip()
            freq     = rest[1].strip()
            rate     = rest[2].strip()
            try:
                signal = int(rest[3].strip())
            except ValueError:
                continue
            security = ":".join(rest[4:]).strip() if len(rest) > 4 else ""

            # Bande déduite de la fréquence
            band = "5 GHz" if freq.startswith("5") else "2.4 GHz"

            # Qualité textuelle du signal (0–100)
            if signal >= 75:
                quality = "Excellent"
            elif signal >= 50:
                quality = "Bon"
            elif signal >= 25:
                quality = "Faible"
            else:
                quality = "Très faible"

            networks.append({
                "in_use":   in_use,
                "ssid":     ssid,
                "bssid":    bssid,
                "chan":     chan,
                "freq":     freq,
                "rate":     rate,
                "signal":   signal,
                "quality":  quality,
                "security": security,
                "band":     band,
            })

        # Réseau actif en premier, puis tri par signal décroissant
        networks.sort(key=lambda n: (not n["in_use"], -n["signal"]))
        result["networks"] = networks

    except Exception:
        result["networks"] = []

    return result
