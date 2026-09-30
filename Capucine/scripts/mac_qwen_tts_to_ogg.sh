#!/usr/bin/env bash
# Exécuté SUR LE MAC via SSH (cf. capucine/mac_generate.py côté Pi) : lit le
# texte à dire sur stdin, génère un vocal via Qwen3-TTS-CustomVoice (modèle
# MLX local, exécuté avec `uvx` pour ne pas gérer un venv dédié à la main)
# puis le convertit en OGG/Opus (mono, 16kHz) — format attendu par Telegram
# pour un message vocal natif (sendVoice).
#
# CustomVoice (voix parmi 9 timbres intégrés + `--instruct` pour le ton) a
# été préféré au modèle "Base" (clonage vocal par référence, ex. voix macOS
# Amélie) : le Base ne supporte aucun contrôle de ton et rendait une diction
# plate jugée peu naturelle, alors qu'aucun des 9 timbres CustomVoice n'est
# nativement français — compromis tranché en faveur du ton sur l'accent
# (décision du 2026-09-27). Les deux modèles sont mutuellement exclusifs :
# CustomVoice rejette --ref_audio.
set -euo pipefail

# Une commande SSH non interactive reçoit un PATH minimal : ni ffmpeg
# (Homebrew) ni uv/uvx (installés dans ~/.local/bin) n'y sont sans ça.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# Rien de ceci n'est en dur : propre à ce Mac / ajustable sans toucher au
# script, cf. capucine/mac_generate.py qui les injecte via SSH.
MODEL_PATH="${CAPUCINE_TTS_MODEL_PATH:?CAPUCINE_TTS_MODEL_PATH doit être défini}"
VOICE="${CAPUCINE_TTS_VOICE:?CAPUCINE_TTS_VOICE doit être défini}"
INSTRUCT="${CAPUCINE_TTS_INSTRUCT:?CAPUCINE_TTS_INSTRUCT doit être défini}"
OUTPUT_PATH="/tmp/capucine-voice.ogg"
TMP_DIR="$(mktemp -d -t capucine-voice)"

trap 'rm -rf "$TMP_DIR"' EXIT

TEXT="$(cat)"

# mlx_audio écrit "<file_prefix>_000.<format>" dans --output_path.
uvx --from mlx-audio mlx_audio.tts.generate \
  --model "$MODEL_PATH" \
  --voice "$VOICE" \
  --instruct "$INSTRUCT" \
  --lang_code fr \
  --output_path "$TMP_DIR" \
  --file_prefix capucine-voice \
  --audio_format wav \
  --text "$TEXT" >&2

ffmpeg -y -i "$TMP_DIR/capucine-voice_000.wav" -c:a libopus -b:a 32k -ar 16000 -ac 1 "$OUTPUT_PATH" >/dev/null
