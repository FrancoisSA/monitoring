"""Cache TTL en mémoire, utilisé par le dashboard pour éviter de refaire un
aller-retour Google Calendar/Tasks à chaque requête HTTP.

Chaque appel API Google (build() + events().list()/tasks().list()) prend
plusieurs centaines de ms (mesuré ~0.5-0.75s sur le Pi). Le dashboard
rafraîchit ses données toutes les 60s côté client, et la page /weekends
interroge en plus /api/events sur 365 jours en parallèle du dashboard
principal : sans cache, ouvrir les deux pages en même temps multiplie ces
appels sans que les données aient eu le temps de changer.
"""
from __future__ import annotations

import time


class TTLCache:
    """Cache clé → valeur avec expiration, sans dépendance externe (Redis,
    etc.) : volume de données personnel, un seul processus dashboard."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: "dict[str, tuple[float, object]]" = {}

    def get_or_set(self, key: str, compute):
        """Retourne la valeur en cache si elle a moins de `ttl_seconds`,
        sinon appelle `compute()` et met à jour le cache."""
        now = time.monotonic()
        cached = self._store.get(key)
        if cached is not None and now - cached[0] < self._ttl:
            return cached[1]
        value = compute()
        self._store[key] = (now, value)
        return value

    def invalidate(self, prefix: str) -> None:
        """Supprime toutes les entrées dont la clé commence par `prefix` —
        appelé après une écriture (tâche complétée, note modifiée) pour ne
        pas servir une valeur périmée jusqu'à expiration naturelle du TTL."""
        self._store = {k: v for k, v in self._store.items() if not k.startswith(prefix)}
