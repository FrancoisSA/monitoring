"""Transcription vocale (STT) en local sur le Pi, via whisper.cpp — repli
pour /agenda vocal quand le Mac (cf. capucine/mac_stt.py) est injoignable
après le réveil Wake-on-LAN. Contrairement à mac_stt.py, aucun SSH/scp :
le script tourne directement sur la machine qui exécute le service
Capucine (cf. scripts/pi_whisper_transcribe.sh).

whisper.cpp est compilé localement avec les optimisations ARM du Pi 5
(NEON/dotprod) et charge un modèle ggml multilingue téléchargé une fois
(cf. docs — modèle "base" recommandé comme compromis vitesse/précision).
"""
from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

# Livré avec l'application (pas de SSH, donc pas de constante de chemin
# distant comme REMOTE_STT_SCRIPT dans mac_stt.py) : résolu relativement à
# ce fichier pour rester correct quel que soit le répertoire de travail.
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "pi_whisper_transcribe.sh"

RunFn = Callable[["list[str]", dict], "subprocess.CompletedProcess"]


@dataclass(frozen=True)
class PiSttConfig:
    whisper_cli_path: str
    whisper_model_path: str
    timeout_s: int = 60


def _run_local(command: "list[str]", env: dict, timeout_s: int) -> "subprocess.CompletedProcess":
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, env=env)


def transcribe_voice_on_pi(
    config: PiSttConfig,
    local_audio_path: "str | Path",
    run: "RunFn | None" = None,
) -> str:
    """Transcrit un fichier audio (OGG/Opus, message vocal Telegram) en texte,
    via whisper.cpp exécuté en local sur le Pi.

    Même contrat que transcribe_voice_on_mac (capucine/mac_stt.py) : un échec
    est bloquant, toujours levé en exception, à charge de l'appelant
    (service.py::resolve_voice_message) de décider du repli suivant."""
    env = {
        **os.environ,
        "CAPUCINE_WHISPER_CLI": config.whisper_cli_path,
        "CAPUCINE_WHISPER_MODEL": config.whisper_model_path,
    }
    command = ["bash", str(SCRIPT_PATH), str(local_audio_path)]
    run_fn = run or (lambda cmd, e: _run_local(cmd, e, config.timeout_s))
    result = run_fn(command, env)

    if result.returncode != 0:
        raise RuntimeError(
            f"[pi_stt] Échec transcription locale (code {result.returncode}) : {result.stderr.strip()}"
        )

    text = result.stdout.strip()
    if not text:
        raise RuntimeError("[pi_stt] Transcription vide")

    return text
