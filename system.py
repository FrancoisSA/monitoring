"""
system.py — Collecte des métriques système : CPU, RAM, disques, processus et I/O.
"""
import socket
import time

import psutil

from config import WATCH_DISK, WATCH_NIC


# ── Métriques système ──────────────────────────────────────────────────────────

def get_system_stats(monitor_temp: bool = True) -> dict:
    """Retourne CPU, RAM, température et uptime."""
    mem = psutil.virtual_memory()
    cpu_temp = None

    if monitor_temp:
        try:
            temps = psutil.sensors_temperatures()
            for key in ("cpu_thermal", "coretemp", "cpu-thermal"):
                if key in temps and temps[key]:
                    cpu_temp = temps[key][0].current
                    break
        except (AttributeError, NotImplementedError):
            pass

    uptime = time.time() - psutil.boot_time()
    hours, rem = divmod(int(uptime), 3600)
    minutes = rem // 60

    return {
        "cpu_percent":  psutil.cpu_percent(interval=None),
        "cpu_temp":     cpu_temp,
        "mem_total_mb": mem.total / 1024 / 1024,
        "mem_used_mb":  mem.used  / 1024 / 1024,
        "mem_percent":  mem.percent,
        "uptime":       f"{hours}h {minutes:02d}m",
        "hostname":     socket.gethostname(),
    }


def get_top_cpu_procs(n: int = 10) -> list:
    """Retourne les n processus les plus gourmands en CPU."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(procs, key=lambda x: x["cpu_percent"] or 0, reverse=True)[:n]


def get_disk_stats() -> list:
    """Retourne l'utilisation de chaque partition montée."""
    disks = []
    for part in psutil.disk_partitions(all=False):
        if part.fstype in ("squashfs", "tmpfs", "devtmpfs", "overlay", ""):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "device":     part.device,
                "mountpoint": part.mountpoint,
                "fstype":     part.fstype,
                "total_gb":   round(usage.total / 1024 ** 3, 1),
                "used_gb":    round(usage.used  / 1024 ** 3, 1),
                "free_gb":    round(usage.free  / 1024 ** 3, 1),
                "percent":    usage.percent,
            })
        except (PermissionError, OSError):
            continue
    return disks


# ── Suivi des débits I/O disque et réseau ─────────────────────────────────────

class IoTracker:
    """Calcule les débits disque et réseau en MB/s entre deux appels à sample()."""

    def __init__(self):
        self._prev_disk = {}
        self._prev_net  = {}
        self._prev_time = time.time()
        self._snapshot()

    def _snapshot(self):
        try:
            self._prev_disk = psutil.disk_io_counters(perdisk=True)
            self._prev_net  = psutil.net_io_counters(pernic=True)
        except Exception:
            pass
        self._prev_time = time.time()

    def sample(self) -> dict:
        """Retourne les débits en MB/s depuis le dernier appel."""
        now     = time.time()
        elapsed = max(now - self._prev_time, 0.01)
        try:
            disk_now = psutil.disk_io_counters(perdisk=True)
            net_now  = psutil.net_io_counters(pernic=True)
        except Exception:
            return {"disk_read_mb": 0, "disk_write_mb": 0, "net_rx_mb": 0, "net_tx_mb": 0}

        result = {}

        d_prev = self._prev_disk.get(WATCH_DISK)
        d_now  = disk_now.get(WATCH_DISK)
        if d_prev and d_now:
            result["disk_read_mb"]  = round((d_now.read_bytes  - d_prev.read_bytes)  / elapsed / 1_048_576, 3)
            result["disk_write_mb"] = round((d_now.write_bytes - d_prev.write_bytes) / elapsed / 1_048_576, 3)
        else:
            result["disk_read_mb"] = result["disk_write_mb"] = 0

        n_prev = self._prev_net.get(WATCH_NIC)
        n_now  = net_now.get(WATCH_NIC)
        if n_prev and n_now:
            result["net_rx_mb"] = round((n_now.bytes_recv - n_prev.bytes_recv) / elapsed / 1_048_576, 3)
            result["net_tx_mb"] = round((n_now.bytes_sent - n_prev.bytes_sent) / elapsed / 1_048_576, 3)
        else:
            result["net_rx_mb"] = result["net_tx_mb"] = 0

        self._prev_disk = disk_now
        self._prev_net  = net_now
        self._prev_time = now
        return result
