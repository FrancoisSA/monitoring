#!/usr/bin/env python3
"""
monitor.py — Live system & web server monitor for Raspberry Pi 5
Usage:
  python monitor.py                        # config.json + auto-detect
  python monitor.py -c /path/to/cfg.json  # custom config
  python monitor.py -u http://host1 ...   # URLs ad-hoc
  python monitor.py --check-interval 30   # HTTP check every 30s (default 10)

Raccourcis clavier :
  f   Afficher / masquer le panneau Finder (liens SMB cliquables)
  q   Quitter
"""

import argparse
import collections
import configparser
import json
import os
import queue
import re
import select
import socket
import subprocess
import sys
import termios
import threading
import time
import tty
from datetime import datetime

import psutil
import requests
from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console(force_terminal=True, highlight=False)
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
SMB_CONF    = "/etc/samba/smb.conf"

# Liste des noms de processus web courants pour la détection automatique
WEB_NAMES = {
    "nginx", "apache2", "httpd", "lighttpd", "caddy", "haproxy",
    "gunicorn", "uvicorn", "hypercorn", "daphne",
    "node", "nodejs", "ruby", "rails",
    "php-fpm", "php", "tomcat",
    "python3", "python",
}
# Ports web courants pour la détection automatique des serveurs
WEB_PORTS  = {80, 443, 3000, 4000, 5000, 8000, 8008, 8080, 8443, 8888, 9000}
SPINNER    = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

# Skip-list for smb.conf sections that aren't real file shares
SMB_META_SECTIONS = {"global", "printers", "print$", "ipc$"}

# Interfaces et disques à surveiller pour les flux
WATCH_DISK = "sda"
WATCH_NIC  = "eth0"

# Services systemd gérés par le monitor
KNOWN_SERVICES = [
    {"key": "1", "service": "hcautomation", "label": "HC Automation", "port": 3141},
    {"key": "2", "service": "budget-web",   "label": "Budget Web",    "port": 5000},
    {"key": "3", "service": "budget-bot",   "label": "Budget Bot",    "port": None},
    {"key": "4", "service": "jeffrey",      "label": "Jeffrey",       "port": None},
    {"key": "5", "service": "monitor",      "label": "Pi Monitor",    "port": 9090},
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def build_bar(pct: float, width: int = 18) -> str:
    """Construit une barre de progression textuelle pour les pourcentages."""
    filled = max(0, min(width, int(pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


def pct_color(pct: float, warn: float = 60, crit: float = 85) -> str:
    """Retourne la couleur Rich selon le niveau d'utilisation."""
    return "bright_green" if pct < warn else ("bright_yellow" if pct < crit else "bright_red")


def latency_color(ms: float) -> str:
    """Retourne la couleur selon la latence HTTP."""
    return "bright_green" if ms < 200 else ("bright_yellow" if ms < 800 else "bright_red")


# ── System ─────────────────────────────────────────────────────────────────────

def get_system_stats(monitor_temp: bool = True) -> dict:
    """Collecte les statistiques système principales : CPU, RAM, température."""
    mem = psutil.virtual_memory()
    cpu_temp = None
    if monitor_temp:
        try:
            # Récupération de la température CPU via psutil (spécifique Raspberry Pi)
            temps = psutil.sensors_temperatures()
            for key in ("cpu_thermal", "coretemp", "cpu-thermal"):
                if key in temps and temps[key]:
                    cpu_temp = temps[key][0].current
                    break
        except (AttributeError, NotImplementedError):
            # Gestion des cas où les capteurs ne sont pas disponibles
            pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),  # Utilisation CPU instantanée
        "cpu_temp": cpu_temp,  # Température CPU en °C
        "mem_total_mb": mem.total / 1024 / 1024,  # RAM totale en MB
        "mem_used_mb": mem.used / 1024 / 1024,   # RAM utilisée en MB
        "mem_percent": mem.percent,  # Pourcentage RAM utilisée
    }


# ── Top CPU ────────────────────────────────────────────────────────────────────

def get_top_cpu_procs(n: int = 10) -> list[dict]:
    """Retourne les n processus consommant le plus de CPU."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(procs, key=lambda x: x["cpu_percent"] or 0, reverse=True)[:n]


def render_top_procs(procs: list[dict]) -> Table:
    t = Table(box=box.ROUNDED, title="[bold bright_cyan]Top CPU[/]",
              title_style="bold bright_cyan", border_style="bright_cyan",
              show_header=True, padding=(0, 1))
    t.add_column("Processus", style="bold bright_white", min_width=20)
    t.add_column("PID",       justify="right", style="color(248)", min_width=7)
    t.add_column("CPU %",     justify="right", min_width=8)
    t.add_column("RAM %",     justify="right", min_width=8)
    for p in procs:
        cpu = p["cpu_percent"] or 0.0
        ram = p["memory_percent"] or 0.0
        t.add_row(
            p["name"] or "?",
            str(p["pid"]),
            Text(f"{cpu:5.1f}%", style=f"bold {pct_color(cpu, 30, 70)}"),
            Text(f"{ram:5.1f}%", style=pct_color(ram)),
        )
    return t


# ── Disks ──────────────────────────────────────────────────────────────────────

def get_disk_stats() -> list[dict]:
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay", ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total_gb": usage.total / 1024 ** 3,
                "used_gb": usage.used / 1024 ** 3,
                "free_gb": usage.free / 1024 ** 3,
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            continue
    return disks


# ── I/O flux (réseau + disque) ─────────────────────────────────────────────────

class IoTracker:
    """
    Calcule des débits MB/s en faisant la différence entre deux appels.
    Utilise psutil.disk_io_counters et psutil.net_io_counters.
    """

    def __init__(self) -> None:
        self._prev_disk: dict = {}
        self._prev_net:  dict = {}
        self._prev_time: float = time.time()
        self._snapshot()

    def _snapshot(self) -> None:
        t = time.time()
        try:
            d = psutil.disk_io_counters(perdisk=True)
            n = psutil.net_io_counters(pernic=True)
        except Exception:
            return
        self._prev_disk = d
        self._prev_net  = n
        self._prev_time = t

    def sample(self) -> dict:
        """Return dict with MB/s values since last call."""
        now   = time.time()
        elapsed = max(now - self._prev_time, 0.01)

        try:
            disk_now = psutil.disk_io_counters(perdisk=True)
            net_now  = psutil.net_io_counters(pernic=True)
        except Exception:
            return self._empty()

        result: dict = {"elapsed": elapsed}

        # ── disque ──
        d_prev = self._prev_disk.get(WATCH_DISK)
        d_now  = disk_now.get(WATCH_DISK)
        if d_prev and d_now:
            result["disk_read_mb"]  = (d_now.read_bytes  - d_prev.read_bytes)  / elapsed / 1_048_576
            result["disk_write_mb"] = (d_now.write_bytes - d_prev.write_bytes) / elapsed / 1_048_576
            result["disk_read_ms"]  = (d_now.read_time   - d_prev.read_time)   / elapsed   # ms/s → utilisation %
            result["disk_write_ms"] = (d_now.write_time  - d_prev.write_time)  / elapsed
        else:
            result.update({"disk_read_mb": 0, "disk_write_mb": 0,
                           "disk_read_ms": 0, "disk_write_ms": 0})

        # ── réseau ──
        n_prev = self._prev_net.get(WATCH_NIC)
        n_now  = net_now.get(WATCH_NIC)
        if n_prev and n_now:
            result["net_rx_mb"] = (n_now.bytes_recv - n_prev.bytes_recv) / elapsed / 1_048_576
            result["net_tx_mb"] = (n_now.bytes_sent - n_prev.bytes_sent) / elapsed / 1_048_576
        else:
            result.update({"net_rx_mb": 0, "net_tx_mb": 0})

        self._prev_disk = disk_now
        self._prev_net  = net_now
        self._prev_time = now
        return result

    @staticmethod
    def _empty() -> dict:
        return {"elapsed": 1, "disk_read_mb": 0, "disk_write_mb": 0,
                "disk_read_ms": 0, "disk_write_ms": 0,
                "net_rx_mb": 0, "net_tx_mb": 0}


def throughput_bar(mbps: float, max_mbps: float = 120, width: int = 16) -> str:
    pct = min(mbps / max_mbps, 1.0) * 100
    filled = max(0, int(pct / 100 * width))
    return "█" * filled + "░" * (width - filled)


def throughput_color(mbps: float) -> str:
    if mbps < 10:
        return "bright_cyan"
    if mbps < 60:
        return "bright_green"
    if mbps < 100:
        return "bright_yellow"
    return "bright_red"


def render_flux(io: dict) -> Panel:
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    t.add_column("Label", style="bold bright_white", min_width=16)
    t.add_column("Bar",   min_width=20)
    t.add_column("MB/s",  justify="right", min_width=10)
    t.add_column("Note",  style="color(248)",        min_width=18)

    def row(label: str, mbps: float, note: str = "") -> None:
        color = throughput_color(mbps)
        bar   = Text()
        bar.append("[", style="bold bright_white")
        bar.append(throughput_bar(mbps), style=color)
        bar.append("]", style="bold bright_white")
        val = Text(f"{mbps:6.2f} MB/s", style=f"bold {color}")
        t.add_row(label, bar, val, note)

    row(f"Disque {WATCH_DISK} écriture", io["disk_write_mb"],
        f"util. {min(io['disk_write_ms'], 100):.0f} ms/s")
    row(f"Disque {WATCH_DISK} lecture",  io["disk_read_mb"],
        f"util. {min(io['disk_read_ms'],  100):.0f} ms/s")
    row(f"Réseau {WATCH_NIC} RX",        io["net_rx_mb"],  "← reçu (TM écrit)")
    row(f"Réseau {WATCH_NIC} TX",        io["net_tx_mb"],  "→ envoyé")

    # Diagnostic goulot
    dw = io["disk_write_mb"]
    nr = io["net_rx_mb"]
    if nr > 1 or dw > 1:
        if dw < nr * 0.5:
            bottleneck = Text("⚠ Goulot : écriture disque plus lente que le réseau", style="bold bright_yellow")
        elif nr < dw * 0.5:
            bottleneck = Text("⚠ Goulot : réseau plus lent que la capacité disque", style="bold bright_yellow")
        else:
            bottleneck = Text("✓ Réseau et disque équilibrés", style="bright_green")
    else:
        bottleneck = Text("– Pas de flux actif", style="color(244)")

    return Panel(
        Group(t, bottleneck),
        title="[bold bright_cyan]Flux I/O — Time Machine[/]",
        border_style="bright_cyan",
        box=box.ROUNDED,
        padding=(0, 1),
    )


# ── Top CPU processes ──────────────────────────────────────────────────────────



# ── Web processes ──────────────────────────────────────────────────────────────

def scan_web_processes() -> list[dict]:
    found: dict[int, dict] = {}
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


# ── SMB / Finder ───────────────────────────────────────────────────────────────

def get_smb_shares() -> list[dict]:
    """
    Parse /etc/samba/smb.conf and return a list of browseable file shares.
    The special [homes] section is resolved to the current user's home share.
    """
    if not os.path.exists(SMB_CONF):
        return []

    cp = configparser.RawConfigParser(strict=False)
    try:
        cp.read(SMB_CONF)
    except Exception:
        return []

    hostname = socket.gethostname() + ".local"
    current_user = os.environ.get("USER") or os.environ.get("LOGNAME") or "user"
    shares = []

    for section in cp.sections():
        low = section.lower()
        if low in SMB_META_SECTIONS:
            continue

        comment = cp.get(section, "comment", fallback="")
        path    = cp.get(section, "path",    fallback="")

        if low == "homes":
            # [homes] → each user gets a share named after themselves
            smb_url = f"smb://{hostname}/{current_user}"
            shares.append({
                "name":    f"{current_user} (home)",
                "path":    f"/home/{current_user}",
                "comment": comment or "Répertoire personnel",
                "url":     smb_url,
            })
        else:
            smb_url = f"smb://{hostname}/{section}"
            shares.append({
                "name":    section,
                "path":    path,
                "comment": comment,
                "url":     smb_url,
            })

    return shares


def is_samba_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            if "smbd" in proc.info["name"].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def render_finder(shares: list[dict], samba_ok: bool) -> Panel:
    """
    Render the Finder panel.
    URLs are OSC 8 hyperlinks → clickable in iTerm2 / Terminal.app.
    Clicking opens Finder on the connected Mac directly.
    """
    if not samba_ok:
        body = Text()
        body.append("  Samba n'est pas en cours d'exécution.\n", style="bold bright_red")
        body.append("  Démarrer : ", style="color(248)")
        body.append("sudo systemctl start smbd", style="bold bright_yellow")
        return Panel(body, title="[bold bright_magenta]Finder (SMB)[/]",
                     border_style="bright_magenta", box=box.ROUNDED)

    if not shares:
        body = Text("  Aucun partage trouvé dans smb.conf", style="color(244)")
        return Panel(body, title="[bold bright_magenta]Finder (SMB)[/]",
                     border_style="bright_magenta", box=box.ROUNDED)

    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column("Partage",  style="bold bright_magenta", min_width=20)
    t.add_column("Chemin",   style="color(248)",          min_width=22)
    t.add_column("Lien",     min_width=38)

    for s in shares:
        # OSC 8 hyperlink — clickable in modern terminals
        link_text = Text()
        link_text.append(s["url"], style=f"bold bright_cyan link {s['url']}")
        name_text = Text()
        name_text.append(s["name"], style="bold bright_magenta")
        if s["comment"]:
            name_text.append(f"\n{s['comment']}", style="color(244)")
        t.add_row(name_text, s["path"], link_text)

    hint = Text()
    hint.append("\n  Finder > ", style="color(248)")
    hint.append("Aller > Se connecter au serveur…", style="color(248) italic")
    hint.append("  (⌘K)", style="color(248)")
    hint.append("  puis coller l'URL ci-dessus.", style="color(248)")

    return Panel(
        Group(t, hint),
        title="[bold bright_magenta]Finder — Partages SMB[/]",
        box=box.ROUNDED,
        border_style="bright_magenta",
    )


# ── HTTP checks ────────────────────────────────────────────────────────────────

def check_server(name: str, url: str, timeout: int) -> dict:
    t0 = time.time()
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True)
        ms = (time.time() - t0) * 1000
        return {"name": name, "url": url, "status": resp.status_code,
                "elapsed_ms": ms, "ok": resp.status_code < 400, "error": None}
    except requests.exceptions.ConnectionError:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": "Connexion refusée"}
    except requests.exceptions.Timeout:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": f"Timeout >{timeout}s"}
    except Exception as e:
        return {"name": name, "url": url, "status": None,
                "elapsed_ms": None, "ok": False, "error": str(e)[:35]}


def build_server_list(procs: list[dict], config_servers: list[dict]) -> list[dict]:
    seen: set[str] = set()
    servers: list[dict] = []
    for s in config_servers:
        if s["url"] not in seen:
            servers.append({"name": s["name"], "url": s["url"]})
            seen.add(s["url"])
    for p in procs:
        if p["url"] not in seen:
            servers.append({"name": p["name"], "url": p["url"]})
            seen.add(p["url"])
    return servers


# ── Render ─────────────────────────────────────────────────────────────────────

def get_services_status() -> list[dict]:
    """Retourne le statut systemd de chaque service connu."""
    results = []
    for svc in KNOWN_SERVICES:
        try:
            r = subprocess.run(
                ["systemctl", "show", svc["service"],
                 "--property=ActiveState,ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=5,
            )
            active, since = "unknown", ""
            for line in r.stdout.splitlines():
                if line.startswith("ActiveState="):
                    active = line.split("=", 1)[1].strip()
                elif line.startswith("ActiveEnterTimestamp="):
                    since = line.split("=", 1)[1].strip()
        except Exception:
            active, since = "unknown", ""
        results.append({**svc, "active": active, "since": since})
    return results


def render_services(services: list[dict], selected: str | None = None) -> Table:
    """Affiche le panneau des services systemd avec statut et uptime."""
    t = Table(box=box.ROUNDED, title="[bold bright_cyan]Services[/]",
              title_style="bold bright_cyan", border_style="bright_cyan",
              show_header=True, padding=(0, 1))
    t.add_column("",        min_width=3,  style="bold bright_white")   # touche
    t.add_column("Service", min_width=16, style="bold bright_white")
    t.add_column("Port",    min_width=6,  justify="right", style="bright_yellow")
    t.add_column("État",    min_width=10, justify="center")
    t.add_column("Depuis",  min_width=20, style="color(248)")

    for s in services:
        key_text = Text(f"[{s['key']}]",
                        style="bold bright_cyan" if s["key"] == selected else "color(244)")
        if s["active"] == "active":
            state = Text("● running", style="bold bright_green")
        elif s["active"] == "inactive":
            state = Text("○ stopped", style="bold color(244)")
        elif s["active"] == "failed":
            state = Text("✗ failed",  style="bold bright_red")
        else:
            state = Text(s["active"], style="color(244)")

        # Formater le timestamp "Tue 2026-04-07 10:36:18 CEST" → "07/04 10:36"
        since = s.get("since", "")
        try:
            dt = datetime.strptime(since[:19], "%a %Y-%m-%d %H:%M:%S")
            since = dt.strftime("%d/%m %H:%M")
        except Exception:
            since = "—"

        t.add_row(key_text, s["label"], str(s["port"]), state, since)

    # Hint selon sélection
    if selected:
        hint = Text()
        hint.append("  Service sélectionné → ", style="color(248)")
        hint.append("[r]", style="bold bright_cyan")
        hint.append(" Restart  ", style="color(248)")
        hint.append("[a]", style="bold bright_green")
        hint.append(" Start  ", style="color(248)")
        hint.append("[x]", style="bold bright_red")
        hint.append(" Stop  ", style="color(248)")
        hint.append("[Esc]", style="color(244)")
        hint.append(" Annuler", style="color(248)")
        return Group(t, hint)  # type: ignore[return-value]
    return t


# ── Voltage ────────────────────────────────────────────────────────────────────

# Masque des bits de throttling Raspberry Pi
_THROTTLE_BITS = {
    0x000001: "⚡ Sous-tension",
    0x000002: "🔥 Fréq. plafonnée",
    0x000004: "🐢 Throttling actif",
    0x000008: "🌡 Limite temp. douce",
    0x010000: "⚡ Sous-tension (hist.)",
    0x020000: "🔥 Fréq. plafonnée (hist.)",
    0x040000: "🐢 Throttling (hist.)",
    0x080000: "🌡 Limite temp. (hist.)",
}
# Bits critiques = problème actif en ce moment
_CRITICAL_BITS = 0x000001 | 0x000004


def get_voltage() -> dict:
    """Lit la tension cœur et le statut de throttling via vcgencmd."""
    volt, throttled = None, 0
    try:
        out = subprocess.check_output(["vcgencmd", "measure_volts", "core"],
                                      text=True, timeout=2)
        m = re.search(r"volt=([\d.]+)V", out)
        if m:
            volt = float(m.group(1))
    except Exception:
        pass
    try:
        out = subprocess.check_output(["vcgencmd", "get_throttled"],
                                      text=True, timeout=2)
        m = re.search(r"throttled=(0x[0-9a-fA-F]+)", out)
        if m:
            throttled = int(m.group(1), 16)
    except Exception:
        pass
    return {"volt": volt, "throttled": throttled, "ts": time.time()}


class VoltageHistory:
    """
    Historique de tension sur deux niveaux :
      - recent   : échantillons toutes les 5s sur la dernière heure (max 720)
      - hourly   : moyenne horaire sur les dernières 24h (max 24)
    """
    SAMPLE_INTERVAL = 5          # secondes entre deux échantillons
    RECENT_MAXLEN   = 720        # 3600s / 5s = 720 points = 1 heure
    HOURLY_MAXLEN   = 24         # 24 heures

    def __init__(self) -> None:
        self.recent: collections.deque = collections.deque(maxlen=self.RECENT_MAXLEN)
        self.hourly: collections.deque = collections.deque(maxlen=self.HOURLY_MAXLEN)
        # Événements de sous-tension : garde les 50 derniers
        self.undervolt_events: collections.deque = collections.deque(maxlen=50)
        self._last_sample  = 0.0
        self._hour_buf:  list[float] = []
        self._hour_start = time.time()
        self._prev_critical = False   # pour détecter le front montant

    def add(self, v: dict, cpu_percent: float = 0.0) -> None:
        """Appeler à chaque tick ; échantillonne toutes les 5s."""
        now = time.time()
        if now - self._last_sample < self.SAMPLE_INTERVAL:
            return
        self._last_sample = now

        if v["volt"] is None:
            return

        critical = bool(v["throttled"] & _CRITICAL_BITS)

        # Enregistrer l'événement de sous-tension au front montant uniquement
        if critical and not self._prev_critical:
            self.undervolt_events.append({
                "ts":         now,
                "volt":       v["volt"],
                "cpu":        cpu_percent,
                "throttled":  v["throttled"],
            })
        self._prev_critical = critical

        # Stocker l'échantillon récent
        self.recent.append({"volt": v["volt"], "throttled": v["throttled"], "ts": now})

        # Accumuler pour la moyenne horaire
        self._hour_buf.append(v["volt"])

        # Consolider si une heure s'est écoulée
        if now - self._hour_start >= 3600 and self._hour_buf:
            avg  = sum(self._hour_buf) / len(self._hour_buf)
            low  = any(r["throttled"] & _CRITICAL_BITS
                       for r in list(self.recent)
                       if r["ts"] >= self._hour_start)
            self.hourly.append({
                "ts":   self._hour_start,
                "avg":  avg,
                "min":  min(self._hour_buf),
                "max":  max(self._hour_buf),
                "low":  low,
                "n":    len(self._hour_buf),
            })
            self._hour_buf  = []
            self._hour_start = now


_SPARK = "▁▂▃▄▅▆▇█"

def _sparkline(values: list[float], width: int = 40) -> str:
    """Génère une sparkline unicode à partir d'une liste de valeurs."""
    if not values:
        return "─" * width
    mn, mx = min(values), max(values)
    rng = mx - mn or 0.001
    chars = []
    step = max(1, len(values) // width)
    for i in range(0, len(values), step):
        v = values[i]
        idx = int((v - mn) / rng * (len(_SPARK) - 1))
        chars.append(_SPARK[idx])
    return "".join(chars[-width:])


def render_voltage(v: dict, history: VoltageHistory) -> Panel:
    throttled = v["throttled"]
    volt      = v["volt"]
    critical  = bool(throttled & _CRITICAL_BITS)

    # ── Ligne de statut ──────────────────────────────────────────────────────
    status = Text()
    if volt is not None:
        color = "bright_red" if critical else ("bright_yellow" if volt < 1.0 else "bright_green")
        status.append(f"Tension cœur : ", style="bold bright_white")
        status.append(f"{volt:.4f} V", style=f"bold {color}")
    else:
        status.append("Tension : indisponible", style="color(244)")

    if throttled:
        active_flags = [label for bit, label in _THROTTLE_BITS.items() if throttled & bit]
        status.append("   ", style="")
        status.append("  ".join(active_flags), style="bold bright_red" if critical else "bright_yellow")
    else:
        status.append("   ✓ Aucun problème détecté", style="bright_green")

    # ── Sparkline dernière heure ─────────────────────────────────────────────
    recent_vals = [r["volt"] for r in history.recent]
    spark_text  = Text()
    spark_text.append("1h  [", style="color(248)")
    if recent_vals:
        mn, mx = min(recent_vals), max(recent_vals)
        rng    = mx - mn or 0.001
        for r in list(history.recent)[-60:]:   # derniers 60 points affichés
            idx   = int((r["volt"] - mn) / rng * (len(_SPARK) - 1))
            color = "bright_red" if r["throttled"] & _CRITICAL_BITS else "bright_green"
            spark_text.append(_SPARK[idx], style=color)
        spark_text.append(f"]  min {mn:.3f}V  max {mx:.3f}V  "
                          f"({len(recent_vals)} pts)", style="color(248)")
    else:
        spark_text.append("en attente d'échantillons…", style="color(244)")
        spark_text.append("]", style="color(248)")

    # ── Tableau horaire 24h ──────────────────────────────────────────────────
    ht = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    ht.add_column("Heure",   style="color(248)", min_width=6)
    ht.add_column("Moy.",    justify="right", min_width=9)
    ht.add_column("Min",     justify="right", min_width=9)
    ht.add_column("Max",     justify="right", min_width=9)
    ht.add_column("Pts",     justify="right", style="color(248)", min_width=5)
    ht.add_column("Alerte",  min_width=6)

    for h in list(history.hourly):
        hcolor = "bright_red" if h["low"] else "bright_green"
        ht.add_row(
            datetime.fromtimestamp(h["ts"]).strftime("%H:%M"),
            Text(f"{h['avg']:.4f}V", style=f"bold {hcolor}"),
            Text(f"{h['min']:.4f}V", style="color(248)"),
            Text(f"{h['max']:.4f}V", style="color(248)"),
            str(h["n"]),
            Text("⚡ LOW", style="bold bright_red") if h["low"] else Text("OK", style="bright_green"),
        )
    if not history.hourly:
        ht.add_row(Text("—  données horaires disponibles après 1h", style="color(244)"),
                   "", "", "", "", "")

    # ── Événements de sous-tension avec CPU ─────────────────────────────────
    et = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    et.add_column("Heure",    style="color(248)", min_width=9)
    et.add_column("Tension",  justify="right",    min_width=9)
    et.add_column("CPU",      justify="right",    min_width=8)
    et.add_column("Flags",    style="bright_yellow", min_width=30)

    events = list(history.undervolt_events)
    if events:
        for e in reversed(events[-10:]):   # 10 derniers, plus récent en premier
            flags = "  ".join(lbl for bit, lbl in _THROTTLE_BITS.items()
                              if e["throttled"] & bit and bit < 0x10000)
            et.add_row(
                datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S"),
                Text(f"{e['volt']:.4f}V", style="bold bright_red"),
                Text(f"{e['cpu']:.1f}%",  style=pct_color(e["cpu"])),
                flags or "—",
            )
    else:
        et.add_row(Text("Aucun événement de sous-tension enregistré", style="bright_green"),
                   "", "", "")

    ev_title = Text()
    ev_title.append(f"⚡ Événements sous-tension ({len(events)} total)", style="bold bright_red")

    border = "bright_red" if critical else "bright_cyan"
    title  = "[bold bright_red]⚡ Voltage[/]" if critical else "[bold bright_cyan]Voltage[/]"
    return Panel(Group(status, spark_text, ht, ev_title, et), title=title,
                 border_style=border, box=box.ROUNDED, padding=(0, 1))


def render_system(stats: dict) -> Panel:
    cpu, mem = stats["cpu_percent"], stats["mem_percent"]
    t = Text()
    t.append("CPU  [", style="bold bright_white")
    t.append(build_bar(cpu), style=pct_color(cpu))
    t.append("] ", style="bold bright_white")
    t.append(f"{cpu:5.1f}%", style=f"bold {pct_color(cpu)}")
    if stats["cpu_temp"] is not None:
        t.append(f"   {stats['cpu_temp']:.1f}°C", style=pct_color(stats["cpu_temp"], 65, 80))
    t.append("\nRAM  [", style="bold bright_white")
    t.append(build_bar(mem), style=pct_color(mem))
    t.append("] ", style="bold bright_white")
    t.append(f"{mem:5.1f}%", style=f"bold {pct_color(mem)}")
    t.append(f"   {stats['mem_used_mb']:.0f} / {stats['mem_total_mb']:.0f} MB", style="color(248)")
    return Panel(t, title="[bold bright_cyan]Système[/]", border_style="bright_cyan",
                 box=box.ROUNDED, padding=(0, 1))


def render_disks(disks: list[dict]) -> Table:
    t = Table(box=box.ROUNDED, title="[bold bright_cyan]Disques[/]",
              title_style="bold bright_cyan", border_style="bright_cyan",
              show_header=True, padding=(0, 1))
    t.add_column("Montage",      style="bold bright_white", min_width=14)
    t.add_column("Périphérique", style="color(248)",        min_width=12)
    t.add_column("FS",           style="color(248)",        min_width=6)
    t.add_column("Utilisation",  min_width=26)
    t.add_column("Libre",        justify="right", style="bright_white", min_width=9)
    t.add_column("Total",        justify="right", style="color(248)",   min_width=9)
    for d in disks:
        pct = d["percent"]
        bar = Text()
        bar.append("[", style="bold bright_white")
        bar.append(build_bar(pct), style=pct_color(pct))
        bar.append("] ", style="bold bright_white")
        bar.append(f"{pct:.1f}%", style=f"bold {pct_color(pct)}")
        t.add_row(d["mountpoint"], d["device"].split("/")[-1], d["fstype"],
                  bar, f"{d['free_gb']:.1f} GB", f"{d['total_gb']:.1f} GB")
    return t


def render_processes(procs: list[dict]) -> Table:
    t = Table(box=box.ROUNDED, title="[bold bright_cyan]Processus web[/]",
              title_style="bold bright_cyan", border_style="bright_cyan",
              show_header=True, padding=(0, 1))
    t.add_column("Processus", style="bold bright_white", min_width=14)
    t.add_column("PID",       justify="right", style="color(248)", min_width=7)
    t.add_column("Port",      justify="right", style="bright_yellow", min_width=7)
    t.add_column("URL",       style="bright_cyan",    min_width=28)
    if not procs:
        t.add_row(Text("Aucun serveur web détecté", style="color(244)"), "", "", "")
    else:
        for p in sorted(procs, key=lambda x: x["port"]):
            t.add_row(p["name"], str(p["pid"]), str(p["port"]), p["url"])
    return t


def render_servers(results: list[dict], last_check: float, checking: bool) -> Table:
    age  = int(time.time() - last_check)
    hint = Text(" (vérification…)", style="bright_cyan") if checking else Text(f" (il y a {age}s)", style="color(244)")
    title = Text.assemble(Text("Serveurs HTTP", style="bold bright_cyan"), hint)
    t = Table(box=box.ROUNDED, title=title,
              title_style="bold bright_cyan", border_style="bright_cyan",
              show_header=True, padding=(0, 1))
    t.add_column("Nom",     style="bold bright_white", min_width=16)
    t.add_column("URL",     style="color(248)",        min_width=30)
    t.add_column("HTTP",    justify="center", min_width=6)
    t.add_column("Latence", justify="right",  min_width=10)
    t.add_column("État",    justify="center", min_width=14)
    for r in results:
        lat = (Text(f"{r['elapsed_ms']:.0f} ms", style=latency_color(r["elapsed_ms"]))
               if r["elapsed_ms"] else Text("—", style="bright_red"))
        state = (Text("● UP", style="bold bright_green") if r["ok"]
                 else Text(f"✗ {r['error'] or 'Erreur'}", style="bold bright_red"))
        t.add_row(r["name"], r["url"],
                  Text(str(r["status"]) if r["status"] else "—",
                       style="bright_green" if r["ok"] else "bright_red"),
                  lat, state)
    return t


def render_processes_and_servers(
    procs: list[dict],
    results: list[dict],
    last_check: float,
    checking: bool,
) -> Table:
    """Affiche uniquement les Serveurs HTTP."""
    row = Table(box=None, show_header=False, padding=0, expand=True)
    row.add_column("main")
    row.add_row(render_servers(results, last_check, checking))
    return row


def render_shutdown_confirm() -> Panel:
    body = Text(justify="center")
    body.append("\n  Voulez-vous vraiment éteindre le Raspberry Pi ?\n\n", style="bold bright_white")
    body.append("  [", style="bold bright_white")
    body.append("o", style="bold bright_green")
    body.append("]", style="bold bright_white")
    body.append(" Oui, éteindre", style="bright_green")
    body.append("        ", style="")
    body.append("  [", style="bold bright_white")
    body.append("n", style="bold bright_red")
    body.append("]", style="bold bright_white")
    body.append(" Non, annuler\n", style="bright_red")
    return Panel(
        body,
        title="[bold bright_red]⚠  ARRÊT DU RASPBERRY PI[/]",
        border_style="bright_red",
        box=box.DOUBLE,
        padding=(0, 2),
    )


def build_display(
    stats: dict,
    disks: list[dict],
    procs: list[dict],
    server_results: list[dict],
    last_check: float,
    checking: bool,
    tick: int,
    show_finder: bool,
    smb_shares: list[dict],
    samba_ok: bool,
    io: dict,
    shutdown_confirm: bool = False,
    show_top_cpu: bool = False,
    top_procs: list[dict] | None = None,
    services: list[dict] | None = None,
    selected_service: str | None = None,
    voltage: dict | None = None,
    volt_history: VoltageHistory | None = None,
) -> Group:
    sp = SPINNER[tick % len(SPINNER)]
    ts = datetime.now().strftime("%H:%M:%S")

    up    = sum(1 for r in server_results if r["ok"])
    total = len(server_results)
    up_color = "bright_green" if up == total else ("bright_yellow" if up > 0 else "bright_red")

    finder_label  = "Masquer Finder"  if show_finder  else "Ouvrir dans Finder"
    top_cpu_label = "Masquer Top CPU" if show_top_cpu else "Top CPU"
    footer = Text()
    footer.append(f"  {up}/{total} serveurs UP   ", style=f"bold {up_color}")
    footer.append("[f]", style="bold bright_magenta")
    footer.append(f" {finder_label}", style="color(248)")
    footer.append("   ")
    footer.append("[c]", style="bold bright_cyan")
    footer.append(f" {top_cpu_label}", style="color(248)")
    footer.append("   ")
    footer.append("[1]…[5]", style="bold bright_cyan")
    footer.append(" Services", style="color(248)")
    footer.append("   ")
    footer.append("[t]", style="bold bright_yellow")
    footer.append(" Terminal", style="color(248)")
    footer.append("   ")
    footer.append("[s]", style="bold bright_red")
    footer.append(" Éteindre", style="color(248)")
    footer.append("   ")
    footer.append("[q]", style="bold bright_red")
    footer.append(" Quitter", style="color(248)")

    # ── Ligne 1 : Système | Top CPU (côte à côte quand actif) ────────────────
    if show_top_cpu:
        row1 = Table(box=None, show_header=False, padding=0, expand=True)
        row1.add_column("sys",  ratio=1)
        row1.add_column("top",  ratio=2)
        row1.add_row(render_system(stats), render_top_procs(top_procs or []))
    else:
        row1 = render_system(stats)

    # ── Ligne 2 : Disques | Flux I/O côte à côte ─────────────────────────────
    row2 = Table(box=None, show_header=False, padding=0, expand=True)
    row2.add_column("disks", ratio=3)
    row2.add_column("flux",  ratio=2)
    row2.add_row(render_disks(disks), render_flux(io))

    parts: list = [
        Text(f"  {sp}  Raspberry Pi 5 — Monitor   {ts}",
             style="bold bright_cyan", justify="center"),
        footer,
        row1,
        row2,
        render_services(services or [], selected_service),
    ]
    if voltage is not None and volt_history is not None:
        parts.append(render_voltage(voltage, volt_history))
    parts.append(render_servers(server_results, last_check, checking))
    if show_finder:
        parts.append(render_finder(smb_shares, samba_ok))
    if shutdown_confirm:
        parts.append(render_shutdown_confirm())

    return Group(*parts)


# ── Keyboard ───────────────────────────────────────────────────────────────────

def start_keyboard_listener(stop_event: threading.Event) -> queue.SimpleQueue:
    """
    Read keypresses in a background thread using cbreak mode (no echo,
    no buffering, Ctrl+C still works). Returns a queue fed with characters.
    stop_event permet d'arrêter proprement le thread (ex: avant un sous-shell).
    """
    key_q: queue.SimpleQueue = queue.SimpleQueue()

    def _reader() -> None:
        if not sys.stdin.isatty():
            return
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not stop_event.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    key_q.put(ch)
        except Exception:
            pass
        finally:
            try:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                pass

    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return key_q


# ── Config ─────────────────────────────────────────────────────────────────────

def load_config(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"servers": [], "timeout": 5}
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON invalide dans la config :[/] {e}")
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Live monitor — Raspberry Pi 5")
    parser.add_argument("-c", "--config", default=CONFIG_FILE)
    parser.add_argument("-u", "--urls", nargs="+", metavar="URL")
    parser.add_argument("-t", "--timeout", type=int, default=None)
    parser.add_argument("--check-interval", type=int, default=10,
                        help="Intervalle des vérifications HTTP en secondes (défaut : 10)")
    args = parser.parse_args()

    cfg           = load_config(args.config)
    timeout       = args.timeout or cfg.get("timeout", 5)
    check_interval = args.check_interval

    config_servers: list[dict] = (
        [{"name": u, "url": u} for u in args.urls]
        if args.urls else cfg.get("servers", [])
    )

    # Prime CPU counter
    psutil.cpu_percent(interval=None)
    time.sleep(0.2)

    # I/O tracker (delta MB/s)
    io_tracker = IoTracker()

    # Initial data
    stats        = get_system_stats(cfg.get("monitor_temperature", True))
    disks        = get_disk_stats()
    procs        = scan_web_processes()
    smb_shares   = get_smb_shares()
    samba_ok     = is_samba_running()
    server_list  = build_server_list(procs, config_servers)
    server_results: list[dict] = [check_server(s["name"], s["url"], timeout)
                                   for s in server_list]
    last_check   = time.time()
    io_stats     = io_tracker.sample()
    top_procs    = get_top_cpu_procs()

    # Shared state
    lock             = threading.Lock()
    checking         = False
    show_finder      = False
    show_top_cpu     = False
    top_procs:    list[dict] = []
    services:     list[dict] = get_services_status()
    selected_svc: str | None = None   # clé "1"/"2"/"3" du service sélectionné
    volt_history  = VoltageHistory()
    voltage       = get_voltage()
    volt_history.add(voltage)
    shutdown_confirm = False

    def http_checker_loop() -> None:
        nonlocal server_results, last_check, checking, procs
        while True:
            time.sleep(check_interval)
            with lock:
                current_procs = procs
                checking = True
            servers     = build_server_list(current_procs, config_servers)
            new_results = [check_server(s["name"], s["url"], timeout) for s in servers]
            with lock:
                server_results = new_results
                last_check     = time.time()
                checking       = False

    threading.Thread(target=http_checker_loop, daemon=True).start()

    listener_stop = threading.Event()
    key_q = start_keyboard_listener(listener_stop)

    tick         = 0
    open_terminal = False

    with Live(screen=True, refresh_per_second=2, console=console) as live:
        try:
            while True:
                time.sleep(1)
                tick += 1

                # Handle keypresses
                while True:
                    try:
                        ch = key_q.get_nowait()
                        if shutdown_confirm:
                            if ch in ("o", "O"):
                                live.stop()
                                subprocess.run(["sudo", "shutdown", "-h", "now"])
                                return
                            else:
                                shutdown_confirm = False
                        elif ch in ("q", "Q", "\x03"):   # q or Ctrl+C
                            return
                        elif ch in ("f", "F"):
                            show_finder  = not show_finder
                            samba_ok     = is_samba_running()
                            smb_shares   = get_smb_shares()
                        elif ch in ("c", "C"):
                            show_top_cpu = not show_top_cpu
                            if show_top_cpu:
                                top_procs = get_top_cpu_procs()
                        elif ch in ("1", "2", "3", "4", "5"):
                            # Sélectionner un service (bascule si déjà sélectionné)
                            selected_svc = None if selected_svc == ch else ch
                        elif ch in ("r", "R") and selected_svc:
                            svc = next((s for s in KNOWN_SERVICES if s["key"] == selected_svc), None)
                            if svc:
                                subprocess.Popen(["sudo", "systemctl", "restart", svc["service"]])
                                selected_svc = None
                                services = get_services_status()
                        elif ch in ("a", "A") and selected_svc:
                            svc = next((s for s in KNOWN_SERVICES if s["key"] == selected_svc), None)
                            if svc:
                                subprocess.Popen(["sudo", "systemctl", "start", svc["service"]])
                                selected_svc = None
                                services = get_services_status()
                        elif ch in ("x", "X") and selected_svc:
                            svc = next((s for s in KNOWN_SERVICES if s["key"] == selected_svc), None)
                            if svc:
                                subprocess.Popen(["sudo", "systemctl", "stop", svc["service"]])
                                selected_svc = None
                                services = get_services_status()
                        elif ch == "\x1b":   # Echap — annuler sélection
                            selected_svc = None
                        elif ch in ("s", "S") and not selected_svc:
                            shutdown_confirm = True
                        elif ch in ("t", "T"):
                            open_terminal = True
                    except queue.Empty:
                        break

                # Ouvre un shell interactif — reprend le monitor à la sortie
                if open_terminal:
                    open_terminal = False
                    listener_stop.set()        # arrête le thread clavier (restaure le terminal)
                    time.sleep(0.15)           # laisse le thread se terminer proprement
                    live.stop()
                    print("\n\033[1;33m─── Terminal Pi — tape 'exit' pour revenir au monitor ───\033[0m\n")
                    subprocess.run([os.environ.get("SHELL", "/bin/bash"), "-i"])
                    print("\n\033[1;33m─── Retour au monitor… ───\033[0m\n")
                    time.sleep(0.3)
                    listener_stop.clear()
                    key_q = start_keyboard_listener(listener_stop)
                    live.start(refresh=False)
                    continue

                stats     = get_system_stats(cfg.get("monitor_temperature", True))
                io_stats  = io_tracker.sample()
                procs     = scan_web_processes()
                top_procs = get_top_cpu_procs()
                if tick % 5 == 0:
                    disks    = get_disk_stats()
                    services = get_services_status()
                voltage = get_voltage()
                volt_history.add(voltage, stats["cpu_percent"])
                if show_top_cpu:
                    top_procs = get_top_cpu_procs()

                with lock:
                    sr  = server_results
                    lc  = last_check
                    chk = checking

                live.update(build_display(
                    stats, disks, procs, sr, lc, chk, tick,
                    show_finder, smb_shares, samba_ok,
                    io_stats, shutdown_confirm, show_top_cpu, top_procs,
                    services, selected_svc,
                    voltage, volt_history,
                ))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
