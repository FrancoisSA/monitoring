"""Client Google Gmail — sous-ensemble nécessaire au scan des emails
[AGENDA PRO] : rechercher, lire le contenu, marquer comme lu.

Porté depuis prj-jeffrey/services/google_gmail.py (list_emails et
mark_as_unread non repris, non utilisés par le flux calendrier — cf. plan
de portage).
"""
from __future__ import annotations

import base64
import binascii
import logging

from bs4 import BeautifulSoup
from googleapiclient.discovery import build

from capucine.google_auth import get_google_credentials

logger = logging.getLogger(__name__)


def _extract_parts(payload: dict) -> "tuple[str, str]":
    """
    Extrait le corps texte et HTML d'un payload Gmail en parcourant
    récursivement les parties MIME imbriquées (multipart/multipart, etc.).

    Le texte brut (text/plain) est privilégié ; le HTML n'est converti en
    texte que s'il n'existe pas de partie text/plain.

    Returns:
        (body_text, body_html)
    """
    plain_parts: "list[str]" = []
    html_parts: "list[str]" = []

    def _walk(part: dict):
        mime = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")

        if mime == "text/plain" and data:
            try:
                plain_parts.append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))
            except (binascii.Error, ValueError):
                pass
        elif mime == "text/html" and data:
            try:
                html_parts.append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))
            except (binascii.Error, ValueError):
                pass
        for sub in part.get("parts", []):
            _walk(sub)

    if "parts" in payload:
        for part in payload["parts"]:
            _walk(part)
    else:
        _walk(payload)

    body_text = "\n".join(plain_parts)
    body_html = "\n".join(html_parts)
    if not body_text and body_html:
        body_text = BeautifulSoup(body_html, "html.parser").get_text()

    return body_text, body_html


def _collect_attachments(payload: dict) -> "list[dict]":
    """Parcourt récursivement le payload pour lister les pièces jointes."""
    attachments = []

    def _walk(part: dict):
        if part.get("filename"):
            body = part.get("body", {})
            attachments.append({
                "filename": part["filename"],
                "mime_type": part.get("mimeType", "application/octet-stream"),
                "size": body.get("size", 0),
            })
        for sub in part.get("parts", []):
            _walk(sub)

    if "parts" in payload:
        for part in payload["parts"]:
            _walk(part)

    return attachments


class GmailClient:
    def __init__(self, credentials_file: str, token_file: str) -> None:
        self._credentials_file = credentials_file
        self._token_file = token_file

    def _get_service(self):
        creds = get_google_credentials(self._credentials_file, self._token_file)
        return build("gmail", "v1", credentials=creds)

    def get_email(self, email_id: str) -> dict:
        """
        Récupère le contenu complet d'un email : sujet, expéditeur, date,
        corps (texte et html), pièces jointes.
        """
        service = self._get_service()
        msg = service.users().messages().get(userId="me", id=email_id, format="full").execute()

        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "(No Subject)")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date_str = next((h["value"] for h in headers if h["name"] == "Date"), "")

        body_text, body_html = _extract_parts(payload)
        attachments = _collect_attachments(payload)

        return {
            "id": email_id,
            "subject": subject,
            "from": sender,
            "date": date_str,
            "body_text": body_text,
            "body_html": body_html,
            "attachments": attachments,
            "is_unread": "UNREAD" in msg["labelIds"],
        }

    def search_emails(self, keyword: str, max_results: int = 10) -> "list[dict]":
        """Recherche des emails contenant un mot-clé dans le sujet/contenu."""
        service = self._get_service()
        result = service.users().messages().list(userId="me", maxResults=max_results, q=keyword).execute()

        messages = result.get("messages", [])
        emails = []
        for msg in messages:
            # Un message listé peut avoir été supprimé entre le list et le
            # get : on l'ignore plutôt que de faire échouer toute la recherche.
            try:
                emails.append(self.get_email(msg["id"]))
            except Exception as e:
                logger.warning("[google_gmail] Impossible de lire l'email %s : %s", msg.get("id"), e)
        return emails

    def mark_as_read(self, email_id: str) -> bool:
        """Marque un email comme lu."""
        service = self._get_service()
        service.users().messages().modify(userId="me", id=email_id, body={"removeLabelIds": ["UNREAD"]}).execute()
        return True
