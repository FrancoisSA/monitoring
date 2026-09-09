#!/usr/bin/env bash
# Déclenche un agent Capucine planifié (ex. cron quotidien -> /presse) sans
# relancer tout le service Python — écrit simplement la commande sur le
# socket Unix du service déjà démarré (cf. capucine/service.py::serve_trigger_socket).
#
# Usage : trigger.sh <commande>   (ex. trigger.sh presse)
set -euo pipefail

COMMAND="${1:?Usage: trigger.sh <commande, ex. presse>}"
DIR="$(cd "$(dirname "$0")/.." && pwd)"
SOCKET_PATH="${CAPUCINE_SOCKET_PATH:-/tmp/capucine.sock}"
LOG_FILE="$DIR/trigger.log"

if ! "$DIR/venv/bin/python3" - "$COMMAND" "$SOCKET_PATH" <<'PYEOF'
import socket
import sys

command, socket_path = sys.argv[1], sys.argv[2]
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
    sock.settimeout(5)
    sock.connect(socket_path)
    sock.sendall(command.encode("utf-8"))
PYEOF
then
    echo "$(date -Iseconds) [ERROR] échec déclenchement /$COMMAND (socket $SOCKET_PATH injoignable)" >> "$LOG_FILE"
    exit 1
fi
