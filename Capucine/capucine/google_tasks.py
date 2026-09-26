"""Client Google Tasks — CRUD sur les tâches, utilisé par le dashboard web.

Porté depuis prj-jeffrey/services/google_tasks.py, adapté au style
d'injection de dépendances de Capucine (cf. capucine/google_calendar.py).
"""
from __future__ import annotations

from datetime import datetime

import pytz
from googleapiclient.discovery import build

from capucine.google_auth import get_google_credentials

_DEFAULT_TASKLIST_ID = "@default"


class GoogleTasksClient:
    def __init__(self, credentials_file: str, token_file: str, timezone: str) -> None:
        self._credentials_file = credentials_file
        self._token_file = token_file
        self._tz = pytz.timezone(timezone)

    def _get_service(self):
        creds = get_google_credentials(self._credentials_file, self._token_file)
        return build("tasks", "v1", credentials=creds)

    def list_tasks(self, max_results: int = 20, show_completed: bool = False) -> "list[dict]":
        """Liste les tâches de la liste par défaut."""
        service = self._get_service()
        result = service.tasks().list(
            tasklist=_DEFAULT_TASKLIST_ID,
            maxResults=max_results,
            showCompleted=show_completed,
            showHidden=show_completed,
        ).execute()

        return [
            {
                "id": t.get("id"),
                "title": t.get("title", ""),
                "due": t.get("due"),  # Format RFC 3339
                "notes": t.get("notes", ""),
                "status": t.get("status", "needsAction"),
            }
            for t in result.get("items", [])
        ]

    def _to_utc_rfc3339(self, due: str) -> str:
        dt = datetime.fromisoformat(due)
        if dt.tzinfo is None:
            dt = self._tz.localize(dt)
        return dt.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    def add_task(self, title: str, due: "str | None" = None, notes: "str | None" = None) -> dict:
        """Ajoute une nouvelle tâche."""
        service = self._get_service()
        task_body = {"title": title}
        if due:
            # Google Tasks attend RFC 3339 en UTC (suffixe Z).
            task_body["due"] = self._to_utc_rfc3339(due)
        if notes:
            task_body["notes"] = notes

        result = service.tasks().insert(tasklist=_DEFAULT_TASKLIST_ID, body=task_body).execute()
        return {"id": result["id"], "title": result.get("title"), "due": result.get("due")}

    def complete_task(self, task_id: str) -> dict:
        """Marque une tâche comme complétée."""
        service = self._get_service()
        task = service.tasks().get(tasklist=_DEFAULT_TASKLIST_ID, task=task_id).execute()
        task["status"] = "completed"

        result = service.tasks().update(tasklist=_DEFAULT_TASKLIST_ID, task=task_id, body=task).execute()
        return {"id": result["id"], "title": result.get("title"), "status": result.get("status")}

    def delete_task(self, task_id: str) -> bool:
        """Supprime une tâche."""
        service = self._get_service()
        service.tasks().delete(tasklist=_DEFAULT_TASKLIST_ID, task=task_id).execute()
        return True

    def update_task(
        self, task_id: str, title: "str | None" = None, due: "str | None" = None, notes: "str | None" = None
    ) -> dict:
        """Modifie une tâche existante."""
        service = self._get_service()
        task = service.tasks().get(tasklist=_DEFAULT_TASKLIST_ID, task=task_id).execute()

        if title is not None:
            task["title"] = title
        if due:
            task["due"] = self._to_utc_rfc3339(due)
        if notes is not None:
            task["notes"] = notes

        result = service.tasks().update(tasklist=_DEFAULT_TASKLIST_ID, task=task_id, body=task).execute()
        return {"id": result["id"], "title": result.get("title"), "due": result.get("due")}

    def search_tasks(self, keyword: str) -> "list[dict]":
        """Recherche des tâches contenant un mot-clé dans le titre ou les notes."""
        all_tasks = self.list_tasks(max_results=100, show_completed=False)
        keyword_lower = keyword.lower()
        return [
            t for t in all_tasks
            if keyword_lower in t["title"].lower() or keyword_lower in (t["notes"] or "").lower()
        ]
