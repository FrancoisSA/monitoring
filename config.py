"""
config.py — Constantes et chargement de la configuration pour Pi Monitor.
"""
import json
import os

# ── Chemins ────────────────────────────────────────────────────────────────────

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
SMB_CONF    = "/etc/samba/smb.conf"

# Interface réseau et disque surveillés pour les métriques I/O
WATCH_DISK = "sda"
WATCH_NIC  = "eth0"

# ── Services systemd gérés ─────────────────────────────────────────────────────

KNOWN_SERVICES = [
    {"key": "1", "service": "hcautomation", "label": "HC Automation", "port": 3141},
    {"key": "2", "service": "budget-web",   "label": "Budget Web",    "port": 5000},
    {"key": "3", "service": "budget-bot",   "label": "Budget Bot",    "port": None},
    {"key": "4", "service": "jeffrey",      "label": "Jeffrey",       "port": None},
    {"key": "5", "service": "monitor",      "label": "Pi Monitor",    "port": 9090},
]

# ── Détection des serveurs web ──────────────────────────────────────────────────

WEB_NAMES = {
    "nginx", "apache2", "httpd", "lighttpd", "caddy", "haproxy",
    "gunicorn", "uvicorn", "hypercorn", "daphne",
    "node", "nodejs", "ruby", "rails",
    "php-fpm", "php", "tomcat", "python3", "python",
}
WEB_PORTS = {80, 443, 3000, 4000, 5000, 8000, 8008, 8080, 8443, 8888, 9000}

# ── Partages Samba — sections ignorées ────────────────────────────────────────

SMB_META_SECTIONS = {"global", "printers", "print$", "ipc$"}

# ── Bits de throttling Raspberry Pi ───────────────────────────────────────────

THROTTLE_LABELS = {
    0x000001: "Sous-tension",
    0x000002: "Fréquence plafonnée",
    0x000004: "Throttling actif",
    0x000008: "Limite température",
    0x010000: "Sous-tension (hist.)",
    0x020000: "Fréq. plafonnée (hist.)",
    0x040000: "Throttling (hist.)",
    0x080000: "Limite temp. (hist.)",
}
CRITICAL_BITS = 0x000001 | 0x000004


# ── Chargement de la configuration JSON ───────────────────────────────────────

def load_config() -> dict:
    """Lit config.json et retourne la configuration, ou des valeurs par défaut."""
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {"servers": [], "timeout": 5}
