"""
services.py — Statut des services systemd et des partages Samba.
"""
import configparser
import os
import socket
import subprocess
import time
from datetime import datetime

from config import KNOWN_SERVICES, SMB_CONF, SMB_META_SECTIONS

# Chemin absolu — le service systemd a un PATH limité à venv/bin
SYSTEMCTL = "/usr/bin/systemctl"


def get_services_status() -> list:
    """Retourne l'état actif et la date de démarrage de chaque service connu."""
    results = []
    for svc in KNOWN_SERVICES:
        try:
            r = subprocess.run(
                [SYSTEMCTL, "show", svc["service"],
                 "--property=ActiveState,ActiveEnterTimestamp"],
                capture_output=True, text=True, timeout=5,
            )
            active, since = "unknown", ""
            for line in r.stdout.splitlines():
                if line.startswith("ActiveState="):
                    active = line.split("=", 1)[1].strip()
                elif line.startswith("ActiveEnterTimestamp="):
                    since = line.split("=", 1)[1].strip()
                    try:
                        dt = datetime.strptime(since[:19], "%a %Y-%m-%d %H:%M:%S")
                        since = dt.strftime("%d/%m %H:%M")
                    except Exception:
                        since = "—"
        except Exception:
            active, since = "unknown", "—"
        results.append({**svc, "active": active, "since": since})
    return results


def get_samba_status() -> dict:
    """Retourne l'état (active/inactive) des démons smbd et nmbd."""
    result = {}
    for svc in ("smbd", "nmbd"):
        try:
            out = subprocess.check_output(
                [SYSTEMCTL, "is-active", svc], text=True, timeout=3
            ).strip()
        except subprocess.CalledProcessError as e:
            out = e.output.strip() if e.output else "inactive"
        except Exception:
            out = "unknown"
        result[svc] = out
    return result


def watchdog_samba() -> list:
    """Vérifie smbd et nmbd ; redémarre tout démon non actif.

    Retourne la liste des événements de ce cycle :
      [{"svc": "smbd", "action": "restarted"|"ok"|"failed", "ts": float, "time": str}]
    """
    events = []
    now_str = datetime.now().strftime("%d/%m %H:%M")
    for svc in ("smbd", "nmbd"):
        # Lecture de l'état courant
        try:
            out = subprocess.check_output(
                [SYSTEMCTL, "is-active", svc], text=True, timeout=3
            ).strip()
        except subprocess.CalledProcessError as e:
            out = e.output.strip() if e.output else "inactive"
        except Exception:
            out = "unknown"

        if out == "active":
            events.append({"svc": svc, "action": "ok", "ts": time.time(), "time": now_str})
            continue

        # Démon non actif → tentative de redémarrage
        try:
            r = subprocess.run(
                ["/usr/bin/sudo", SYSTEMCTL, "restart", svc],
                capture_output=True, text=True, timeout=15,
            )
            action = "restarted" if r.returncode == 0 else "failed"
        except Exception:
            action = "failed"

        events.append({"svc": svc, "action": action, "ts": time.time(), "time": now_str})
    return events


def get_smb_shares() -> list:
    """Parse /etc/samba/smb.conf et retourne la liste des partages accessibles."""
    if not os.path.exists(SMB_CONF):
        return []
    cp = configparser.RawConfigParser(strict=False)
    try:
        cp.read(SMB_CONF)
    except Exception:
        return []

    hostname     = socket.gethostname() + ".local"
    current_user = os.environ.get("USER") or os.environ.get("LOGNAME") or "user"
    shares = []

    for section in cp.sections():
        low = section.lower()
        if low in SMB_META_SECTIONS:
            continue
        comment = cp.get(section, "comment", fallback="")
        path    = cp.get(section, "path",    fallback="")
        if low == "homes":
            shares.append({
                "name":    f"{current_user} (home)",
                "path":    f"/home/{current_user}",
                "comment": comment or "Répertoire personnel",
                "url":     f"smb://{hostname}/{current_user}",
            })
        else:
            shares.append({
                "name":    section,
                "path":    path,
                "comment": comment,
                "url":     f"smb://{hostname}/{section}",
            })
    return shares
