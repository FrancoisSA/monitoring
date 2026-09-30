"""Client HTTP minimal pour l'API Telegram Bot — en polling, jamais en
webhook : seules des requêtes sortantes vers api.telegram.org sont
nécessaires, aucun port entrant à ouvrir sur le Raspberry Pi.

Couche de câblage réseau : volontairement peu testée unitairement (cf.
dispatch.py pour la logique testée en profondeur).
"""
from __future__ import annotations

from pathlib import Path

import requests

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramClient:
    def __init__(self, token: str, poll_timeout: int = 30) -> None:
        self._base = _API_BASE.format(token=token)
        self._poll_timeout = poll_timeout

    def get_updates(self, offset: "int | None") -> "list[dict]":
        params = {"timeout": self._poll_timeout}
        if offset is not None:
            params["offset"] = offset
        # +5s de marge sur le timeout HTTP par rapport au long-polling Telegram
        response = requests.get(
            f"{self._base}/getUpdates", params=params, timeout=self._poll_timeout + 5
        )
        response.raise_for_status()
        return response.json().get("result", [])

    def send_message(self, chat_id: int, text: str) -> None:
        response = requests.post(
            f"{self._base}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        response.raise_for_status()

    def send_voice(self, chat_id: int, voice_path: "str | Path") -> None:
        """Envoie un message vocal natif (bulle avec forme d'onde) — le
        fichier doit être en OGG/Opus, format attendu par l'API Telegram."""
        with open(voice_path, "rb") as voice_file:
            response = requests.post(
                f"{self._base}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": voice_file},
                timeout=30,
            )
        response.raise_for_status()

    def download_voice(self, file_id: str, local_path: "str | Path") -> None:
        """Télécharge un message vocal reçu (OGG/Opus) vers `local_path`.

        Deux appels distincts requis par l'API Telegram : getFile résout le
        chemin de stockage interne (`file_path`), puis le fichier lui-même se
        télécharge depuis un domaine différent (api.telegram.org/file/...,
        pas .../bot<token>/... comme les autres méthodes)."""
        response = requests.get(f"{self._base}/getFile", params={"file_id": file_id}, timeout=10)
        response.raise_for_status()
        file_path = response.json()["result"]["file_path"]

        token = self._base.rsplit("/bot", 1)[1]
        file_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        download = requests.get(file_url, timeout=30)
        download.raise_for_status()

        with open(local_path, "wb") as f:
            f.write(download.content)
