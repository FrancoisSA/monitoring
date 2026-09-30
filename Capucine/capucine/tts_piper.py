"""Synthèse vocale locale (Piper) sur le Pi — repli quand le Mac (Qwen3-TTS
via capucine/mac_generate.py::generate_voice_on_mac) est injoignable.

Contrairement au pipeline Mac, tourne directement ici : pas de SSH ni de
réveil, juste un process local (CLI `piper`) suivi d'une conversion ffmpeg
vers OGG/Opus (format attendu par Telegram pour un message vocal natif).
Qualité inférieure à Qwen3-TTS-CustomVoice (voix "medium" vs modèle MLX
dédié), mais toujours disponible même Mac éteint/injoignable — cf. test de
validation du 2026-09-30 (~3.6x plus rapide que le temps réel sur Pi 5).
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

RunFn = Callable[["list[str]", str], "subprocess.CompletedProcess"]
ConvertFn = Callable[[str, str], "subprocess.CompletedProcess"]


def _piper_binary_path() -> str:
    """Chemin absolu du binaire `piper` du venv courant.

    Le service systemd invoque directement venv/bin/python (cf.
    scripts/capucine.service) sans activer le venv : son PATH n'inclut donc
    pas venv/bin/, et un simple `subprocess.run(["piper", ...])` échouerait
    (command not found). `piper` est installé dans le même bin/ que
    l'interpréteur courant (sys.executable) — toujours correct, quel que
    soit le chemin de déploiement (cf. principe des chemins absolus pour les
    binaires système, CLAUDE.md du projet)."""
    return str(Path(sys.executable).parent / "piper")


def _run_piper(command: "list[str]", stdin_text: str) -> "subprocess.CompletedProcess":
    return subprocess.run(command, input=stdin_text, capture_output=True, text=True, timeout=60)


def _run_ffmpeg(wav_path: str, ogg_path: str) -> "subprocess.CompletedProcess":
    return subprocess.run(
        [
            "ffmpeg", "-y", "-i", wav_path,
            "-c:a", "libopus", "-b:a", "32k", "-ar", "16000", "-ac", "1", ogg_path,
        ],
        capture_output=True, text=True, timeout=30,
    )


def generate_voice_with_piper(
    text: str,
    local_output_path: "str | Path",
    model_path: str,
    run: "RunFn | None" = None,
    convert: "ConvertFn | None" = None,
) -> "Path | None":
    """Génère un vocal localement sur le Pi via Piper (voix `model_path`,
    fichier .onnx — son .json associé attendu au même chemin + suffixe).

    Retourne None sur tout échec (Piper absent, modèle introuvable, ffmpeg en
    échec, ou `model_path` vide = Piper non configuré) plutôt que de lever
    une exception : un vocal manqué ne doit jamais priver l'envoi du texte,
    déjà réussi (même contrat que generate_voice_on_mac)."""
    if not model_path:
        return None

    tmp_dir = tempfile.mkdtemp(prefix="capucine-piper-")
    try:
        wav_path = f"{tmp_dir}/voice.wav"
        command = [_piper_binary_path(), "-m", model_path, "-c", f"{model_path}.json", "-f", wav_path]
        try:
            result = (run or _run_piper)(command, text)
        except Exception:  # noqa: BLE001 — un échec Piper ne doit jamais faire planter l'appelant
            logger.exception("[tts_piper] Échec Piper")
            return None

        if result.returncode != 0:
            logger.warning("[tts_piper] Échec Piper (code %s) : %s", result.returncode, result.stderr.strip())
            return None

        try:
            ffmpeg_result = (convert or _run_ffmpeg)(wav_path, str(local_output_path))
        except Exception:  # noqa: BLE001
            logger.exception("[tts_piper] Échec conversion ffmpeg")
            return None

        if ffmpeg_result.returncode != 0:
            logger.warning("[tts_piper] Échec conversion ffmpeg (code %s)", ffmpeg_result.returncode)
            return None

        return Path(local_output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
