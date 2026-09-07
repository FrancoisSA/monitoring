"""Stockage SQLite léger : historique court de conversation par agent.

Un seul fichier, pas de serveur de base de données à administrer — cohérent
avec la contrainte de légèreté CPU/RAM sur le Raspberry Pi.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


class Store:
    """Une connexion SQLite ouverte une fois et réutilisée — pas de coût
    d'ouverture/fermeture à chaque message (service mono-thread, single
    connexion : sans risque de concurrence)."""

    def __init__(self, db_path: "str | Path") -> None:
        self._db_path = str(db_path)
        self._conn = sqlite3.connect(self._db_path)
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    def save_history(self, agent: str, role: str, content: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO history (agent, role, content) VALUES (?, ?, ?)",
                (agent, role, content),
            )

    def get_history(self, agent: str, limit: int = 20) -> "list[tuple[str, str]]":
        """Renvoie les derniers échanges (role, content), du plus ancien au plus récent."""
        rows = self._conn.execute(
            "SELECT role, content FROM history WHERE agent = ? ORDER BY id DESC LIMIT ?",
            (agent, limit),
        ).fetchall()
        return list(reversed(rows))
