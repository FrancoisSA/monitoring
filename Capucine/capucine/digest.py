"""Pipeline partagé par les agents qui condensent des articles RSS en une
revue de presse envoyée sur Telegram (/presse, /renault, ...) : plafond
d'articles, prompt de traduction/résumé, mise en forme du message.

Réglages calibrés empiriquement sur le Pi avec qwen2.5:3b (agent /presse,
30/08-09/09/2026) — au-delà d'une dizaine d'articles ou avec une consigne
plus longue/détaillée, ce modèle décroche et recopie la liste d'entrée telle
quelle (en anglais, non traduite) au lieu de suivre la consigne. Garder le
prompt aussi court et simple que possible.
"""
from __future__ import annotations

import re
from datetime import datetime

from capucine.feeds import FeedEntry

_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

# Reconnaît les lignes produites par le LLM au format "- [Source] phrase"
# (cf. PROMPT_TEMPLATE) pour les redisposer proprement pour Telegram.
_BULLET_LINE_RE = re.compile(r"^-\s*\[(?P<source>[^\]]+)\]\s*(?P<text>.+)$")
_SEPARATOR = "─" * 24

MAX_ENTRIES_FOR_PROMPT = 10

PROMPT_TEMPLATE = (
    "Traduis et résume en français, en une phrase par article, chacun des "
    "articles ci-dessous. Ne recopie pas les titres en anglais : écris une "
    "phrase entièrement nouvelle en français pour chaque article.\n\n"
    "Réponds avec une liste, une ligne par article, au format :\n"
    "- [Source] ta phrase en français\n\n"
    "Articles :\n{articles}"
)


def format_entries(entries: "list[FeedEntry]") -> str:
    return "\n".join(
        f"- [{entry.source}] {entry.title} — {entry.summary}".rstrip(" —")
        for entry in entries
    )


def build_prompt(entries: "list[FeedEntry]") -> str:
    """Trie par récence et plafonne à MAX_ENTRIES_FOR_PROMPT avant de
    construire le prompt — cf. le commentaire de module sur la fiabilité du
    modèle local au-delà de ce plafond."""
    most_recent = sorted(entries, key=lambda entry: entry.published, reverse=True)
    return PROMPT_TEMPLATE.format(articles=format_entries(most_recent[:MAX_ENTRIES_FOR_PROMPT]))


def format_for_telegram(raw_text: str, title: str, now: "datetime | None" = None) -> str:
    """Redispose la réponse du LLM (lignes "- [Source] phrase") en un message
    Telegram lisible : titre, date, séparateurs, une source par bloc.

    Volontairement en texte brut, sans parse_mode Markdown/HTML : un LLM peut
    produire des caractères qui casseraient le parsing d'entités Telegram et
    feraient échouer l'envoi du message entier — le texte brut s'affiche
    toujours, quoi que le modèle ait généré.
    """
    now = now or datetime.now()
    header = f"{title}\n🗓️ {now.day} {_MONTHS_FR[now.month - 1]} {now.year}\n{_SEPARATOR}"

    blocks = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _BULLET_LINE_RE.match(line)
        if match:
            blocks.append(f"🔹 {match['source'].strip()}\n{match['text'].strip()}")
        else:
            blocks.append(line)

    body = "\n\n".join(blocks) if blocks else raw_text.strip()
    return f"{header}\n\n{body}\n\n{_SEPARATOR}"
