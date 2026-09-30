#!/usr/bin/env bash
# Exécuté SUR LE MAC via SSH (cf. capucine/mac_stt.py côté Pi) : transcrit un
# fichier audio (chemin passé en argument, déjà envoyé par scp) en texte via
# mlx-whisper (modèle MLX local, exécuté avec `uvx` comme le TTS Qwen3, cf.
# mac_qwen_tts_to_ogg.sh — pas de venv dédié à gérer à la main).
set -euo pipefail

# Une commande SSH non interactive reçoit un PATH minimal : ni ffmpeg
# (Homebrew) ni uv/uvx (installés dans ~/.local/bin) n'y sont sans ça.
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

AUDIO_PATH="${1:?Chemin du fichier audio manquant}"
MODEL="${CAPUCINE_STT_MODEL:?CAPUCINE_STT_MODEL doit être défini}"
TMP_DIR="$(mktemp -d -t capucine-stt)"

trap 'rm -rf "$TMP_DIR"' EXIT

# uv/huggingface_hub tentent par défaut une vérification réseau (résolution
# de version, cache HF) à chaque appel — problématique juste après un réveil
# Wake-on-LAN, où le Wi-Fi peut mettre quelques secondes à se reconnecter
# (cause d'un timeout SSH de 120s observé le 2026-09-29). Une fois le paquet
# et le modèle déjà en cache (premier lancement fait manuellement), tout
# fonctionne en local : on force le mode hors-ligne pour ne plus dépendre du
# réseau du tout après ce premier lancement.
export UV_OFFLINE=1
export HF_HUB_OFFLINE=1

uvx --offline --from mlx-whisper mlx_whisper "$AUDIO_PATH" \
  --model "$MODEL" \
  --language French \
  --output-format txt \
  --output-dir "$TMP_DIR" >&2

# mlx_whisper écrit "<nom_du_fichier_source>.txt" dans --output-dir.
BASENAME="$(basename "$AUDIO_PATH")"
cat "$TMP_DIR/${BASENAME%.*}.txt"
