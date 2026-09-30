"""Transcription vocale (STT) sur le Mac, via SSH — symétrique de
capucine/mac_generate.py::generate_voice_on_mac, mais dans l'autre sens :
on pousse un fichier audio vers le Mac (scp) puis on récupère le texte
transcrit sur stdout (mlx-whisper, exécuté avec `uvx` comme le TTS).

Le Mac exécute scripts/mac_whisper_transcribe.sh, déployé sur son disque par
le wizard (cf. scripts/mac_qwen_tts_to_ogg.sh pour le même mécanisme).
"""
from __future__ import annotations

import logging
import shlex
import subprocess
from pathlib import Path
from typing import Callable

from capucine.mac_wake import MacConfig

logger = logging.getLogger(__name__)

REMOTE_STT_SCRIPT = "~/.capucine-mac/mac_whisper_transcribe.sh"
REMOTE_AUDIO_INPUT_PATH = "/tmp/capucine-stt-input.ogg"

RunFn = Callable[["list[str]"], "subprocess.CompletedProcess"]
ScpPushFn = Callable[[MacConfig, str, str], bool]


def _ssh_base_command(config: MacConfig) -> "list[str]":
    return [
        "ssh",
        "-i", config.ssh_key_path,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config.ssh_user}@{config.host}",
    ]


def _run_ssh(command: "list[str]") -> "subprocess.CompletedProcess":
    # Même budget que generate_text_on_mac (mac_generate.py) : le chargement
    # du modèle mlx-whisper en mémoire à chaque appel (pas de serveur
    # persistant) plus la transcription d'un vocal de plusieurs dizaines de
    # secondes peuvent dépasser largement le temps d'un simple aller-retour
    # SSH (mesuré <1s en conditions normales, cf. incident du 2026-09-29).
    return subprocess.run(command, capture_output=True, text=True, timeout=300)


def _scp_push(config: MacConfig, local_path: str, remote_path: str) -> bool:
    result = subprocess.run(
        [
            "scp",
            "-i", config.ssh_key_path,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            local_path,
            f"{config.ssh_user}@{config.host}:{remote_path}",
        ],
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


def transcribe_voice_on_mac(
    config: MacConfig,
    local_audio_path: "str | Path",
    run: "RunFn | None" = None,
    scp_push: "ScpPushFn | None" = None,
) -> str:
    """Transcrit un fichier audio (OGG/Opus, message vocal Telegram) en texte,
    via mlx-whisper sur le Mac.

    Contrairement à generate_voice_on_mac (un vocal manqué ne doit jamais
    priver du texte, donc échec silencieux -> None), un échec ici est
    bloquant : sans texte transcrit, il n'y a rien à router vers un agent.
    Lève systématiquement une exception sur tout échec, à charge de
    l'appelant (service.py) de répondre à l'utilisateur.
    """
    push = scp_push or _scp_push
    if not push(config, str(local_audio_path), REMOTE_AUDIO_INPUT_PATH):
        raise RuntimeError("[mac_stt] Échec de l'envoi du fichier audio vers le Mac")

    # SSH ne forwarde pas l'environnement du client par défaut : le modèle
    # mlx-whisper doit être injecté dans la commande distante elle-même
    # (cf. capucine/mac_generate.py::generate_voice_on_mac, même pattern).
    env_assignment = f"CAPUCINE_STT_MODEL={shlex.quote(config.stt_model)}"
    remote_command = f"{env_assignment} bash {REMOTE_STT_SCRIPT} {shlex.quote(REMOTE_AUDIO_INPUT_PATH)}"
    command = _ssh_base_command(config) + [remote_command]
    result = (run or _run_ssh)(command)

    if result.returncode != 0:
        raise RuntimeError(
            f"[mac_stt] Échec transcription sur le Mac (code {result.returncode}) : {result.stderr.strip()}"
        )

    text = result.stdout.strip()
    if not text:
        raise RuntimeError("[mac_stt] Transcription vide")

    return text
