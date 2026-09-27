"""Réveil et détection de disponibilité du Mac (LM Studio tourne dessus).

Le Pi tente d'abord une connexion SSH directe (rapide si le Mac est déjà
éveillé) ; sinon un paquet magique Wake-on-LAN est envoyé et la connexion
est retentée à intervalle régulier pendant un budget de temps borné — au-delà,
l'appelant doit basculer sur le backend local (Ollama).
"""
from __future__ import annotations

import logging
import socket
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MacConfig:
    host: str
    ssh_user: str
    ssh_key_path: str
    mac_address: str
    model: str
    wake_timeout_s: int = 180
    retry_interval_s: int = 10
    ssh_connect_timeout_s: int = 5
    # Chemin du modèle Qwen3-TTS MLX local sur le Mac, cf.
    # scripts/mac_qwen_tts_to_ogg.sh — SSH ne forwarde pas l'environnement du
    # Pi par défaut, cette valeur doit donc être injectée explicitement dans
    # la commande distante (cf. capucine/mac_generate.py::generate_voice_on_mac).
    tts_model_path: str = ""


def send_wol_packet(
    mac_address: str,
    broadcast_ip: str = "255.255.255.255",
    port: int = 9,
    send_udp: "Callable[[bytes, tuple[str, int]], None] | None" = None,
) -> None:
    """Envoie un paquet magique Wake-on-LAN (6 x 0xFF puis 16 répétitions de
    l'adresse MAC), en UDP broadcast — aucune dépendance externe nécessaire."""
    try:
        mac_bytes = bytes.fromhex(mac_address.replace(":", "").replace("-", ""))
    except ValueError as err:
        raise ValueError(f"[mac_wake] Adresse MAC invalide : {mac_address!r}") from err
    if len(mac_bytes) != 6:
        raise ValueError(f"[mac_wake] Adresse MAC invalide : {mac_address!r}")

    magic_packet = b"\xff" * 6 + mac_bytes * 16

    if send_udp is not None:
        send_udp(magic_packet, (broadcast_ip, port))
        return

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_ip, port))


def is_ssh_reachable(config: MacConfig, run: "Callable[[list[str]], int] | None" = None) -> bool:
    """Vérifie qu'une connexion SSH aboutit, sans exécuter de commande utile
    (juste `true`) — rapide, pour sonder la disponibilité du Mac."""
    command = [
        "ssh",
        "-i", config.ssh_key_path,
        "-o", f"ConnectTimeout={config.ssh_connect_timeout_s}",
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config.ssh_user}@{config.host}",
        "true",
    ]
    if run is not None:
        return run(command) == 0

    result = subprocess.run(
        command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=config.ssh_connect_timeout_s + 5
    )
    return result.returncode == 0


def wait_for_mac(
    config: MacConfig,
    is_reachable: "Callable[[MacConfig], bool]" = is_ssh_reachable,
    send_wol: "Callable[[str], None]" = lambda mac: send_wol_packet(mac),
    sleep: "Callable[[float], None]" = time.sleep,
    now: "Callable[[], float]" = time.monotonic,
) -> bool:
    """Rend le Mac disponible ou renonce après config.wake_timeout_s.

    Ne réveille pas si le Mac répond déjà (chemin rapide, cas le plus
    fréquent en pratique si l'utilisateur travaille dessus). Sinon, envoie un
    paquet Wake-on-LAN puis réessaie à intervalle régulier.
    """
    if is_reachable(config):
        return True

    logger.info("[mac_wake] Mac injoignable, envoi du paquet Wake-on-LAN à %s", config.mac_address)
    send_wol(config.mac_address)

    deadline = now() + config.wake_timeout_s
    while now() < deadline:
        sleep(config.retry_interval_s)
        if is_reachable(config):
            logger.info("[mac_wake] Mac joignable après réveil")
            return True

    logger.warning(
        "[mac_wake] Mac toujours injoignable après %ss, abandon (bascule sur le backend local)",
        config.wake_timeout_s,
    )
    return False
