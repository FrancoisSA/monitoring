#!/usr/bin/env bash
# Exécuté EN LOCAL sur le Pi (pas de SSH, contrairement à
# mac_whisper_transcribe.sh) : repli de transcription vocale quand le Mac
# est injoignable, via whisper.cpp — binaire compilé localement avec les
# optimisations ARM (NEON/dotprod) du Pi 5, cf. capucine/pi_stt.py.
set -euo pipefail

AUDIO_PATH="${1:?Chemin du fichier audio manquant}"
WHISPER_CLI="${CAPUCINE_WHISPER_CLI:?CAPUCINE_WHISPER_CLI doit être défini}"
WHISPER_MODEL="${CAPUCINE_WHISPER_MODEL:?CAPUCINE_WHISPER_MODEL doit être défini}"
# GNU mktemp (Linux/Pi) exige des X finaux dans le template, contrairement au
# mktemp BSD de macOS (cf. mac_whisper_transcribe.sh) qui accepte -t sans.
TMP_DIR="$(mktemp -d -t capucine-pi-stt.XXXXXXXXXX)"
trap 'rm -rf "$TMP_DIR"' EXIT

# whisper.cpp (miniaudio) ne décode pas l'Opus/OGG des vocaux Telegram
# directement (vérifié le 2026-10-03 : "failed to read audio data") — passage
# par ffmpeg vers un WAV 16kHz mono, le format attendu par whisper.cpp.
WAV_PATH="$TMP_DIR/audio.wav"
ffmpeg -y -i "$AUDIO_PATH" -ar 16000 -ac 1 "$WAV_PATH" -loglevel error

"$WHISPER_CLI" -m "$WHISPER_MODEL" -f "$WAV_PATH" --language French -nt
