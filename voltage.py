"""
voltage.py — Lecture de la tension cœur et historique des événements de sous-tension.
"""
import collections
import re
import subprocess
import time
from datetime import datetime

from config import THROTTLE_LABELS, CRITICAL_BITS


# ── Lecture de la tension ──────────────────────────────────────────────────────

def get_voltage() -> dict:
    """Lit la tension cœur et l'état de throttling via vcgencmd."""
    volt, throttled = None, 0

    try:
        out = subprocess.check_output(["/usr/bin/vcgencmd", "measure_volts", "core"],
                                      text=True, timeout=2)
        m = re.search(r"volt=([\d.]+)V", out)
        if m:
            volt = float(m.group(1))
    except Exception:
        pass

    try:
        out = subprocess.check_output(["/usr/bin/vcgencmd", "get_throttled"],
                                      text=True, timeout=2)
        m = re.search(r"throttled=(0x[0-9a-fA-F]+)", out)
        if m:
            throttled = int(m.group(1), 16)
    except Exception:
        pass

    flags    = [label for bit, label in THROTTLE_LABELS.items() if throttled & bit]
    critical = volt is not None and volt < 0.8  # Sous-tension si < 0.8 V
    return {"volt": volt, "throttled": throttled, "flags": flags,
            "critical": critical, "ts": time.time()}


# ── Historique de tension ──────────────────────────────────────────────────────

class VoltageHistory:
    """Stocke l'historique des tensions et détecte les événements de sous-tension."""

    SAMPLE_INTERVAL = 5     # Secondes entre deux échantillons
    RECENT_MAXLEN   = 720   # 1 heure à 5s d'intervalle
    HOURLY_MAXLEN   = 24    # 24 heures

    def __init__(self):
        self.recent:           collections.deque = collections.deque(maxlen=self.RECENT_MAXLEN)
        self.hourly:           collections.deque = collections.deque(maxlen=self.HOURLY_MAXLEN)
        self.undervolt_events: collections.deque = collections.deque(maxlen=50)
        self._last_sample  = 0.0
        self._hour_buf:    list  = []
        self._hour_start   = time.time()
        self._prev_critical = False

    def add(self, v: dict, cpu_percent: float = 0.0):
        """Ajoute un échantillon et enregistre un événement si sous-tension."""
        now = time.time()
        if now - self._last_sample < self.SAMPLE_INTERVAL:
            return
        self._last_sample = now
        if v["volt"] is None:
            return

        critical = bool(v["throttled"] & CRITICAL_BITS)
        if critical and not self._prev_critical:
            self.undervolt_events.append({
                "ts": now, "volt": v["volt"],
                "cpu": cpu_percent, "throttled": v["throttled"],
            })
        self._prev_critical = critical

        self.recent.append({"volt": v["volt"], "throttled": v["throttled"], "ts": now})
        self._hour_buf.append(v["volt"])

        # Calcul de la moyenne horaire
        if now - self._hour_start >= 3600 and self._hour_buf:
            avg = sum(self._hour_buf) / len(self._hour_buf)
            low = any(r["throttled"] & CRITICAL_BITS
                      for r in list(self.recent) if r["ts"] >= self._hour_start)
            self.hourly.append({
                "ts": self._hour_start, "avg": round(avg, 4),
                "min": round(min(self._hour_buf), 4),
                "max": round(max(self._hour_buf), 4),
                "low": low, "n": len(self._hour_buf),
            })
            self._hour_buf   = []
            self._hour_start = now

    def get_recent_volts(self) -> list:
        """Retourne la liste des tensions récentes (pour le graphique sparkline)."""
        return [r["volt"] for r in self.recent]

    def get_events(self) -> list:
        """Retourne les événements de sous-tension formatés pour l'affichage."""
        return [
            {
                "time": datetime.fromtimestamp(e["ts"]).strftime("%d/%m %H:%M:%S"),
                "volt": e["volt"],
                "cpu":  round(e["cpu"], 1),
            }
            for e in reversed(self.undervolt_events)
        ]
