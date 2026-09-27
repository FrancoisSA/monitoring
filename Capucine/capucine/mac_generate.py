"""Génération de texte (LM Studio) et de vocal (Qwen3-TTS via mlx-audio) sur
le Mac, via SSH — orchestré depuis le Pi. Le Mac exécute deux scripts
déployés sur son disque par le wizard (scripts/mac_lmstudio_generate.py,
scripts/mac_qwen_tts_to_ogg.sh).

Le prompt/texte est transmis par stdin (jamais en argument shell) pour éviter
tout problème d'échappement avec du texte arbitraire (guillemets, accents...).
"""
from __future__ import annotations

import logging
import shlex
import subprocess
import time
from pathlib import Path
from typing import Callable

from capucine.llm.base import LLMResponse
from capucine.mac_wake import MacConfig

logger = logging.getLogger(__name__)

REMOTE_GENERATE_SCRIPT = "~/.capucine-mac/mac_lmstudio_generate.py"
REMOTE_TTS_SCRIPT = "~/.capucine-mac/mac_qwen_tts_to_ogg.sh"
REMOTE_VOICE_OUTPUT_PATH = "/tmp/capucine-voice.ogg"

RunFn = Callable[["list[str]", str], "subprocess.CompletedProcess"]


def _ssh_base_command(config: MacConfig) -> "list[str]":
    return [
        "ssh",
        "-i", config.ssh_key_path,
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{config.ssh_user}@{config.host}",
    ]


def _run_ssh(command: "list[str]", stdin_text: str) -> "subprocess.CompletedProcess":
    return subprocess.run(command, input=stdin_text, capture_output=True, text=True, timeout=300)


def _scp_fetch(config: MacConfig, remote_path: str, local_path: str) -> bool:
    result = subprocess.run(
        [
            "scp",
            "-i", config.ssh_key_path,
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            f"{config.ssh_user}@{config.host}:{remote_path}",
            local_path,
        ],
        capture_output=True,
        timeout=30,
    )
    return result.returncode == 0


def generate_text_on_mac(config: MacConfig, prompt: str, run: "RunFn | None" = None) -> LLMResponse:
    """Exécute le script de génération LM Studio sur le Mac via SSH.

    Lève une exception sur tout échec (code de sortie non nul, réponse
    vide) — c'est à l'appelant de décider du repli (cf. digest.py, qui
    bascule sur Ollama)."""
    command = _ssh_base_command(config) + ["python3", REMOTE_GENERATE_SCRIPT, config.model]
    start = time.monotonic()
    result = (run or _run_ssh)(command, prompt)
    latency_ms = (time.monotonic() - start) * 1000

    if result.returncode != 0:
        raise RuntimeError(
            f"[mac_generate] Échec génération sur le Mac (code {result.returncode}) : {result.stderr.strip()}"
        )

    text = result.stdout.strip()
    if not text:
        raise RuntimeError("[mac_generate] Réponse vide du Mac")

    return LLMResponse(text=text, model=config.model, latency_ms=latency_ms)


def generate_voice_on_mac(
    config: MacConfig,
    text: str,
    local_output_path: "str | Path",
    run: "RunFn | None" = None,
    scp: "Callable[[MacConfig, str, str], bool] | None" = None,
) -> "Path | None":
    """Génère un vocal (say + ffmpeg -> OGG/Opus) sur le Mac et le rapatrie.

    Retourne None sur tout échec (SSH, génération, rapatriement) plutôt que
    de lever une exception : un vocal manqué ne doit jamais empêcher l'envoi
    du texte du digest, qui lui a réussi (cf. décision produit)."""
    # SSH ne forwarde pas l'environnement du client par défaut : le chemin du
    # modèle doit être injecté dans la commande distante elle-même (variable
    # d'affectation en tête de la commande, syntaxe shell POSIX standard),
    # pas via l'environnement du process Python local.
    remote_command = (
        f"CAPUCINE_TTS_MODEL_PATH={shlex.quote(config.tts_model_path)} bash {REMOTE_TTS_SCRIPT}"
    )
    command = _ssh_base_command(config) + [remote_command]
    try:
        result = (run or _run_ssh)(command, text)
    except Exception:  # noqa: BLE001 — un échec vocal ne doit jamais remonter, juste être loggé
        logger.exception("[mac_generate] Échec SSH lors de la génération vocale")
        return None

    if result.returncode != 0:
        logger.warning("[mac_generate] Échec génération vocale sur le Mac : %s", result.stderr.strip())
        return None

    fetch = scp or _scp_fetch
    if not fetch(config, REMOTE_VOICE_OUTPUT_PATH, str(local_output_path)):
        logger.warning("[mac_generate] Échec rapatriement du fichier vocal")
        return None

    return Path(local_output_path)
