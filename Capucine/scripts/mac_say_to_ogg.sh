#!/usr/bin/env bash
# Exécuté SUR LE MAC via SSH (cf. capucine/mac_generate.py côté Pi) : lit le
# texte à dire sur stdin, génère un vocal via `say` puis le convertit en
# OGG/Opus (mono, 16kHz) — format attendu par Telegram pour un message vocal
# natif (sendVoice). Le Pi rapatrie ensuite OUTPUT_PATH via scp.
set -euo pipefail

VOICE="${CAPUCINE_SAY_VOICE:-Thomas}"
OUTPUT_PATH="/tmp/capucine-voice.ogg"
# mktemp crée réellement TMP_BASE sur le disque ; AIFF_PATH (avec le suffixe)
# est un chemin distinct que `say` créera séparément — les deux doivent être
# nettoyés, sans quoi TMP_BASE reste orphelin à chaque exécution.
TMP_BASE="$(mktemp -t capucine-voice)"
AIFF_PATH="${TMP_BASE}.aiff"

trap 'rm -f "$TMP_BASE" "$AIFF_PATH"' EXIT

TEXT="$(cat)"
say -v "$VOICE" -o "$AIFF_PATH" "$TEXT"
ffmpeg -y -i "$AIFF_PATH" -c:a libopus -b:a 32k -ar 16000 -ac 1 "$OUTPUT_PATH" >/dev/null 2>&1
