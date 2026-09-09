#!/usr/bin/env python3
"""Exécuté SUR LE MAC via SSH (cf. capucine/mac_generate.py côté Pi) : lit un
prompt sur stdin, interroge l'API locale de LM Studio (compatible OpenAI),
imprime le texte de la réponse sur stdout.

Volontairement sans dépendance tierce (bibliothèque standard uniquement) pour
ne dépendre d'aucun venv sur le Mac — seul un interpréteur python3 système
est nécessaire.
"""
from __future__ import annotations

import json
import sys
import urllib.request

LMSTUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
# Sous le budget SSH côté Pi (300s, cf. mac_generate.py::_run_ssh) pour que
# le Pi voie toujours l'échec réel plutôt qu'un timeout de sa propre connexion.
TIMEOUT_S = 280
MAX_TOKENS = 2000


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: mac_lmstudio_generate.py <model>", file=sys.stderr)
        return 2

    model = sys.argv[1]
    prompt = sys.stdin.read()

    payload = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": MAX_TOKENS,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        LMSTUDIO_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as err:  # noqa: BLE001 — toute erreur doit remonter un message clair sur stderr
        print(f"[mac_lmstudio_generate] Échec appel LM Studio : {err}", file=sys.stderr)
        return 1

    content = data["choices"][0]["message"].get("content", "")
    if not content:
        # Certains modèles "reasoning" consomment tout leur budget de tokens
        # en réflexion cachée sans jamais produire de contenu final (observé
        # avec qwen3.5-9b-mlx) — d'où le choix de qwen3-coder-30b-a3b-instruct-mlx.
        print("[mac_lmstudio_generate] Réponse vide (modèle bloqué en réflexion ?)", file=sys.stderr)
        return 1

    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
