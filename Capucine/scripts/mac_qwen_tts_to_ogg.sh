#!/usr/bin/env bash
# Exécuté SUR LE MAC via SSH (cf. capucine/mac_generate.py côté Pi) : lit le
# texte à dire sur stdin, génère un vocal via Qwen3-TTS (modèle MLX local,
# exécuté avec `uvx` pour ne pas gérer un venv dédié à la main) puis le
# convertit en OGG/Opus (mono, 16kHz) — format attendu par Telegram pour un
# message vocal natif (sendVoice). Remplace l'ancien pipeline `say` (voix
# macOS), dont la meilleure voix installée sur ce Mac s'est avérée nettement
# moins naturelle que Qwen3-TTS à l'écoute (décision du 2026-09-27).
set -euo pipefail

# Une commande SSH non interactive reçoit un PATH minimal : ni ffmpeg
# (Homebrew) ni uv/uvx (installés dans ~/.local/bin) n'y sont sans ça.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# Chemin du modèle Qwen3-TTS MLX local, propre à ce Mac — jamais en dur ici,
# cf. CAPUCINE_TTS_MODEL_PATH injecté par capucine/mac_generate.py.
MODEL_PATH="${CAPUCINE_TTS_MODEL_PATH:?CAPUCINE_TTS_MODEL_PATH doit être défini}"
OUTPUT_PATH="/tmp/capucine-voice.ogg"
TMP_DIR="$(mktemp -d -t capucine-voice)"

trap 'rm -rf "$TMP_DIR"' EXIT

TEXT="$(cat)"

# mlx_audio écrit "<file_prefix>_000.<format>" dans --output_path.
uvx --from mlx-audio mlx_audio.tts.generate \
  --model "$MODEL_PATH" \
  --lang_code fr \
  --output_path "$TMP_DIR" \
  --file_prefix capucine-voice \
  --audio_format wav \
  --text "$TEXT" >&2

ffmpeg -y -i "$TMP_DIR/capucine-voice_000.wav" -c:a libopus -b:a 32k -ar 16000 -ac 1 "$OUTPUT_PATH" >/dev/null
