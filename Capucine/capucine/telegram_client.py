"""Client HTTP minimal pour l'API Telegram Bot — en polling, jamais en
webhook : seules des requêtes sortantes vers api.telegram.org sont
nécessaires, aucun port entrant à ouvrir sur le Raspberry Pi.

Couche de câblage réseau : volontairement peu testée unitairement (cf.
dispatch.py pour la logique testée en profondeur).
"""
from __future__ import annotations

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
