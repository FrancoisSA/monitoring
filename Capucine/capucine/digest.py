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

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from capucine.feeds import FeedEntry
from capucine.llm.base import LLMClient, LLMResponse
from capucine.mac_generate import generate_text_on_mac, generate_voice_on_mac
from capucine.mac_wake import MacConfig, wait_for_mac
from capucine.prompts import load_prompt
from capucine.store import Store
from capucine.tts_piper import generate_voice_with_piper

logger = logging.getLogger(__name__)

_MONTHS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

# Reconnaît les lignes produites par le LLM au format "- [Source] phrase"
# (cf. capucine/prompts/digest.md) pour les redisposer proprement pour Telegram.
_BULLET_LINE_RE = re.compile(r"^-\s*\[(?P<source>[^\]]+)\]\s*(?P<text>.+)$")
_SEPARATOR = "─" * 24

MAX_ENTRIES_FOR_PROMPT = 10

# Modifiable sans toucher au code : cf. capucine/prompts/digest.md.
PROMPT_TEMPLATE = load_prompt("digest")


def format_entries(entries: "list[FeedEntry]") -> str:
    return "\n".join(
        f"- [{entry.source}] {entry.title} — {entry.summary}".rstrip(" —")
        for entry in entries
    )


def _most_recent(entries: "list[FeedEntry]") -> "list[FeedEntry]":
    """Trie par récence et plafonne à MAX_ENTRIES_FOR_PROMPT — cf. le
    commentaire de module sur la fiabilité du modèle local au-delà."""
    return sorted(entries, key=lambda entry: entry.published, reverse=True)[:MAX_ENTRIES_FOR_PROMPT]


def build_prompt(entries: "list[FeedEntry]") -> str:
    return PROMPT_TEMPLATE.format(articles=format_entries(_most_recent(entries)))


def select_unseen_entries(store: Store, agent_name: str, entries: "list[FeedEntry]") -> "list[FeedEntry]":
    """Articles jamais envoyés par cet agent, déjà plafonnés comme dans
    build_prompt : les revues tournent plusieurs fois par jour sur une
    fenêtre de flux plus longue que l'intervalle entre deux envois, sans ce
    filtre chaque revue répéterait la précédente. Les articles au-delà du
    plafond ne sont pas marqués vus et passeront à la revue suivante."""
    unseen = [entry for entry in entries if not store.has_seen(agent_name, entry.link)]
    return _most_recent(unseen)


def mark_entries_sent(store: Store, agent_name: str, entries: "list[FeedEntry]") -> None:
    """À appeler seulement APRÈS une génération réussie : marquer avant
    ferait perdre définitivement les articles si le LLM échoue."""
    for entry in entries:
        store.mark_seen(agent_name, entry.link)
    store.purge_old_seen_links()


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


def text_for_speech(raw_text: str) -> str:
    """Convertit les lignes "- [Source] phrase" en texte naturel pour la
    synthèse vocale (say) : plus de crochets ni de tirets, des phrases
    complètes enchaînées — cf. décision produit : pas de réécriture par LLM
    dédiée, juste un nettoyage du texte déjà rédigé."""
    sentences = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = _BULLET_LINE_RE.match(line)
        if match:
            sentences.append(f"{match['source'].strip()}. {match['text'].strip()}")
        else:
            sentences.append(line)
    return " ".join(sentences)


@dataclass(frozen=True)
class DigestResult:
    response: LLMResponse
    voice_path: "Path | None"


def generate_digest(
    prompt: str,
    fallback_llm_client: LLMClient,
    mac_config: "MacConfig | None" = None,
    voice_output_path: "str | Path | None" = None,
    piper_model_path: "str | None" = None,
    wait_for_mac_fn=wait_for_mac,
    generate_text_fn=generate_text_on_mac,
    generate_voice_fn=generate_voice_on_mac,
    generate_voice_piper_fn=generate_voice_with_piper,
) -> DigestResult:
    """Mécanisme générique de génération d'un digest, réutilisable par tout
    agent (/presse, /renault, /ia, et tout futur agent).

    Texte : serveur LLM du Mac (port 1234) si le Mac est joignable, sinon ou
    en cas d'échec backend local (Ollama, `fallback_llm_client`).
    Vocal (si `voice_output_path`) : choisi indépendamment du texte, cf.
    _generate_voice.
    """
    mac_available = False
    if mac_config is not None:
        try:
            mac_available = wait_for_mac_fn(mac_config)
        except Exception:  # noqa: BLE001 — ex. MAC_ADDRESS mal configurée (mac_wake.send_wol_packet
            # lève ValueError) : ne doit jamais empêcher le repli Ollama, seulement le signaler.
            logger.exception("[digest] Échec de la détection de disponibilité du Mac, repli sur le backend local")

    response = None
    if mac_available:
        try:
            response = generate_text_fn(mac_config, prompt)
        except Exception:  # noqa: BLE001 — un échec côté Mac ne doit jamais empêcher le repli Ollama
            logger.exception("[digest] Échec génération sur le Mac, repli sur le backend local")
    if response is None:
        response = fallback_llm_client.generate(prompt)

    voice_path = None
    if voice_output_path is not None:
        voice_path = _generate_voice(
            text_for_speech(response.text),
            voice_output_path,
            mac_config if mac_available else None,
            piper_model_path,
            generate_voice_fn,
            generate_voice_piper_fn,
        )
    return DigestResult(response=response, voice_path=voice_path)


def _generate_voice(
    speech_text: str,
    voice_output_path: "str | Path",
    mac_config: "MacConfig | None",
    piper_model_path: "str | None",
    generate_voice_fn,
    generate_voice_piper_fn,
) -> "Path | None":
    """Qwen3-TTS sur le Mac dès qu'il est joignable (`mac_config` non None),
    même si le texte vient d'Ollama : la voix Mac (mlx-audio) ne dépend pas
    du serveur LLM du Mac — incident du 2026-10-04, serveur texte arrêté et
    toutes les revues basculées sur Piper alors que le Mac répondait.
    Piper (local au Pi, cf. capucine/tts_piper.py) si le Mac est injoignable
    ou si sa voix échoue ; pas de vocal si `piper_model_path` est vide."""
    if mac_config is not None:
        voice_path = generate_voice_fn(mac_config, speech_text, voice_output_path)
        if voice_path is not None:
            return voice_path
        logger.warning("[digest] Vocal Mac indisponible, repli sur Piper")
    if piper_model_path:
        return generate_voice_piper_fn(speech_text, voice_output_path, piper_model_path)
    return None
