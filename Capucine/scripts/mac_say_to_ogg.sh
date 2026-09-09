#!/usr/bin/env bash
# Exécuté SUR LE MAC via SSH (cf. capucine/mac_generate.py côté Pi) : lit le
# texte à dire sur stdin, génère un vocal via `say` puis le convertit en
# OGG/Opus (mono, 16kHz) — format attendu par Telegram pour un message vocal
# natif (sendVoice). Le Pi rapatrie ensuite OUTPUT_PATH via scp.
set -euo pipefail

# Une commande SSH non interactive reçoit un PATH minimal (pas celui de
# .zprofile/.zshrc) : ffmpeg (Homebrew, /opt/homebrew/bin sur Apple Silicon,
# /usr/local/bin sur Intel) n'y est pas forcément — sans ce PATH étendu,
# ffmpeg échoue en silence (son "command not found" part vers /dev/null,
# redirigé par la ligne ffmpeg elle-même) et le script sort en 127.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

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
# stderr non redirigé vers /dev/null : le Pi (capucine/mac_generate.py) ne
# journalise ce flux qu'en cas d'échec (returncode != 0) — le supprimer ici
# masquerait aussi le vrai message d'erreur en cas de futur problème ffmpeg.
ffmpeg -y -i "$AIFF_PATH" -c:a libopus -b:a 32k -ar 16000 -ac 1 "$OUTPUT_PATH" >/dev/null
