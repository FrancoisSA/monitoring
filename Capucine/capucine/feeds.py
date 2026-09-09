"""Récupération et filtrage des flux RSS/Atom suivis par l'agent /presse.

Module autonome (pas de dépendance à Deps), comme EchoAgent : il ne fait
qu'une chose et reste testable sans réseau réel grâce à `fetch` injectable.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable

import feedparser
import requests

logger = logging.getLogger(__name__)

# Cf. convention CLAUDE.md performance : timeout explicite sur tout appel externe.
_FETCH_TIMEOUT_S = 10

# Résumé max conservé par entrée, une fois le HTML retiré — certains flux
# (ex. Automobile Propre) embarquent l'article entier en HTML dans <description>,
# ce qui gonflerait démesurément le prompt envoyé au LLM en aval.
_MAX_SUMMARY_CHARS = 220

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Certains flux (ex. CleanTechnica, derrière Cloudflare) renvoient 403 sans
# en-tête User-Agent ressemblant à un navigateur — ce n'est pas un contournement
# d'authentification, juste un flux RSS public consulté comme le ferait
# n'importe quel lecteur RSS classique.
_FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


@dataclass(frozen=True)
class FeedEntry:
    source: str
    title: str
    link: str
    summary: str
    published: datetime


def _default_fetch(url: str) -> bytes:
    response = requests.get(url, timeout=_FETCH_TIMEOUT_S, headers=_FETCH_HEADERS)
    response.raise_for_status()
    return response.content


def _clean_summary(raw_summary: str) -> str:
    """Retire le HTML (les flux RSS embarquent souvent des <table>/<img>
    entières dans <description>, ou des entités comme &nbsp;) et tronque à
    _MAX_SUMMARY_CHARS."""
    unescaped = html.unescape(raw_summary)
    text = _WHITESPACE_RE.sub(" ", _HTML_TAG_RE.sub(" ", unescaped)).strip()
    if len(text) > _MAX_SUMMARY_CHARS:
        text = text[:_MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + "…"
    return text


def _parse_published(item) -> "datetime | None":
    parsed_time = item.get("published_parsed") or item.get("updated_parsed")
    if parsed_time is None:
        return None
    return datetime(*parsed_time[:6], tzinfo=timezone.utc)


def _entry_source_and_title(item, feed_source: str) -> "tuple[str, str]":
    """Les agrégateurs (ex. Google News) déclarent un éditeur par article via
    l'élément RSS standard <source>, différent du titre du flux lui-même
    (ex. le nom de la recherche). Sans cet élément (flux "normal", un seul
    éditeur), on retombe sur le titre du flux — comportement inchangé."""
    title = item.get("title", "(sans titre)")
    item_source = item.get("source")
    if not item_source:
        return feed_source, title

    publisher = item_source.get("title") or feed_source
    suffix = f" - {publisher}"
    if title.endswith(suffix):
        title = title[: -len(suffix)]
    return publisher, title


def fetch_recent_entries(
    feed_urls: "list[str]",
    since_hours: int = 30,
    fetch: Callable[[str], bytes] = _default_fetch,
) -> "list[FeedEntry]":
    """Récupère les entrées publiées dans les `since_hours` dernières heures,
    toutes sources confondues.

    Une source en échec (réseau, flux introuvable ou illisible) est ignorée
    et journalisée — ne doit jamais bloquer les autres sources ni faire
    échouer toute la revue de presse.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    entries: "list[FeedEntry]" = []

    for url in feed_urls:
        try:
            raw = fetch(url)
        except Exception:  # noqa: BLE001 — une source en échec ne doit jamais interrompre les autres
            logger.warning("[feeds] Échec récupération %s", url, exc_info=True)
            continue

        parsed = feedparser.parse(raw)
        if not parsed.entries:
            logger.warning("[feeds] Aucune entrée exploitable dans %s (flux vide ou invalide)", url)
            continue

        feed_source = parsed.feed.get("title", url)
        for item in parsed.entries:
            published = _parse_published(item)
            if published is None or published < cutoff:
                continue
            source, title = _entry_source_and_title(item, feed_source)
            entries.append(
                FeedEntry(
                    source=source,
                    title=title,
                    link=item.get("link", ""),
                    summary=_clean_summary(item.get("summary", "")),
                    published=published,
                )
            )

    return entries
