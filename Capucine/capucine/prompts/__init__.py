"""Chargement des prompts LLM depuis des fichiers markdown (ce dossier),
plutôt que des chaînes en dur dans le code — pour pouvoir les relire et les
ajuster sans toucher au code Python. Utilisés par capucine/digest.py,
capucine/agents/synthese.py et capucine/agents/agenda.py.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Charge le contenu du fichier `<name>.md` de ce dossier."""
    path = _PROMPTS_DIR / f"{name}.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(
            f"[prompts] Fichier de prompt introuvable : {path}"
        ) from e
