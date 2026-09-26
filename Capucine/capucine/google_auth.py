"""Authentification Google OAuth2.

Gère le flux d'authentification et le rafraîchissement du token. Le token
est sauvegardé localement pour éviter de se reconnecter à chaque démarrage.

Sur le Pi (serveur headless), le flux OAuth ne peut pas ouvrir de
navigateur. Si le token est absent ou révoqué, une RuntimeError est levée
avec les instructions pour régénérer le token depuis un poste avec
navigateur (cf. USERGUIDE).
"""
from __future__ import annotations

import logging
import os
import sys
import webbrowser

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Scopes nécessaires pour Calendar, Gmail (lecture/marquage lu des emails
# [AGENDA PRO]) et Tasks (dashboard web).
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
]


def _is_headless() -> bool:
    """Détecte un environnement sans navigateur (le Pi en production).
    macOS a toujours un navigateur disponible même sans DISPLAY."""
    if sys.platform == "darwin":
        return False
    try:
        webbrowser.get()
        return False
    except webbrowser.Error:
        return True


def save_token(creds: Credentials, token_file: str) -> None:
    """Écrit le token de manière atomique (fichier temporaire + renommage).

    Évite de laisser un token.json tronqué/corrompu si le processus est
    interrompu en cours d'écriture (kill, disque plein, etc.). En cas
    d'échec de l'écriture, on supprime le fichier temporaire pour ne pas
    laisser de résidu sur disque.
    """
    data = creds.to_json()
    tmp_path = token_file + ".tmp"
    try:
        with open(tmp_path, "w") as token:
            token.write(data)
        os.replace(tmp_path, token_file)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def get_google_credentials(credentials_file: str, token_file: str) -> Credentials:
    """
    Retourne des credentials Google valides.
    - Si token_file existe et est valide, l'utilise directement.
    - Si le token est expiré, le rafraîchit automatiquement.
    - Si le refresh token est révoqué (invalid_grant), supprime le token et
      lève une RuntimeError claire (pas de tentative d'ouvrir un navigateur
      sur le Pi).
    - Si aucun token et environnement headless, lève une RuntimeError avec
      instructions.
    """
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, GOOGLE_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                # On ne détruit le token que si le refresh token est réellement
                # invalide/révoqué (invalid_grant). Sur une erreur réseau
                # transitoire, on préserve le refresh token pour réessayer plus
                # tard — sinon l'utilisateur doit refaire l'OAuth complet.
                error_str = str(e).lower()
                if "invalid_grant" in error_str:
                    logger.error("[google_auth] Refresh token révoqué/invalide : %s", e)
                    try:
                        os.remove(token_file)
                    except OSError:
                        pass
                    creds = None
                else:
                    logger.warning("[google_auth] Échec de refresh (transitoire ?) : %s", e)
                    raise

        if not creds:
            if _is_headless():
                raise RuntimeError(
                    "[google_auth] Token Google absent ou révoqué. Régénérer "
                    f"{token_file} depuis un Mac avec navigateur :\n"
                    "  python3 -c \"from capucine.google_auth import get_google_credentials; "
                    f"get_google_credentials({credentials_file!r}, {token_file!r})\"\n"
                    f"puis : scp {token_file} fsalazar@FSA-PI5.local:/home/fsalazar/03-monitor/Capucine/"
                )

            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, GOOGLE_SCOPES)
            creds = flow.run_local_server(port=0)

        save_token(creds, token_file)

    return creds


def is_credentials_valid(token_file: str) -> bool:
    """
    Vérifie si les credentials Google sont utilisables, sans ouvrir de
    navigateur. Tente un refresh silencieux si le token est expiré.
    Retourne False en cas d'échec (token absent, révoqué, réseau indisponible).
    """
    try:
        if not os.path.exists(token_file):
            return False
        creds = Credentials.from_authorized_user_file(token_file, GOOGLE_SCOPES)
        if creds and creds.valid:
            return True
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            save_token(creds, token_file)
            return True
        return False
    except Exception:
        return False
