"""
Hermes Agent via Mammouth AI - API Flask

Point d'entrée pour discuter avec Hermes via une interface web/API REST.
L'historique de conversation est conservé côté serveur, une session par
navigateur (cookie), bornée à MAX_HISTORY messages.

Usage :
    python -m src.api
"""

from __future__ import annotations

import os
import sys
import time
import uuid
import logging
from typing import Any

# Importer les modules du package (fonctionne en `python -m src.api` et en script direct)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hermes_agent import run_agent, TOOLS

# Import Flask
from flask import Flask, request, jsonify, render_template_string

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# --- Mémoire de conversation (côté serveur, une session par navigateur) ---

MAX_HISTORY = 20          # messages (user + assistant) conservés par session
SESSION_TTL = 2 * 3600    # sessions inactives purgées après 2 h

_sessions: dict[str, dict[str, Any]] = {}


def _purge_stale_sessions() -> None:
    """Supprime les sessions inactives depuis plus de SESSION_TTL secondes."""
    now = time.time()
    for sid in [s for s, d in _sessions.items() if now - d["last_active"] > SESSION_TTL]:
        _sessions.pop(sid, None)


def _get_session() -> tuple[str, list, bool]:
    """
    Retourne (session_id, historique, nouvelle_session).
    L'historique est borné aux MAX_HISTORY derniers messages.
    """
    _purge_stale_sessions()
    sid = request.cookies.get("hermes_session", "")
    is_new = sid not in _sessions
    if is_new:
        sid = uuid.uuid4().hex
        _sessions[sid] = {"messages": [], "last_active": time.time()}
    session = _sessions[sid]
    session["last_active"] = time.time()
    return sid, session["messages"], is_new


def _store(history: list, role: str, content: str) -> None:
    """Ajoute un message à l'historique en le bornant à MAX_HISTORY."""
    history.append({"role": role, "content": content})
    while len(history) > MAX_HISTORY:
        history.pop(0)


# Template HTML du dashboard (à déplacer dans un fichier template)
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hermes Agent</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; }
        h1 { color: #6366f1; }
        .message { margin: 10px 0; padding: 15px; border-radius: 8px; }
        .user { background: #e0e7ff; }
        .assistant { background: #f3f4f6; border-left: 4px solid #6366f1; }
        .tool { background: #dbeafe; font-style: italic; }
        .timestamp { color: #6b7280; font-size: 0.8em; margin-bottom: 5px; }
        .tools { color: #0891b2; font-size: 0.85em; margin-top: 5px; }
        .input-area { display: flex; gap: 10px; margin-top: 20px; }
        input { flex: 1; padding: 10px; border: 2px solid #d1d5db; border-radius: 6px; }
        button { padding: 10px 20px; background: #6366f1; color: white; border: none; border-radius: 6px; cursor: pointer; }
        button:hover { background: #4f46e5; }
        .loading::after { content: " (en train de réfléchir...)"; color: #6b7280; }
    </style>
</head>
<body>
    <h1>🤖 Hermes Agent</h1>
    <div id="chat"></div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Écrivez votre message..." onkeypress="handleKeyPress(event)">
        <button onclick="sendMessage()">Envoyer</button>
    </div>
    <script>
        const chat = document.getElementById('chat');

        function renderMessage(role, content, timestamp, tools) {
            const div = document.createElement('div');
            div.className = 'message ' + role;
            let html = '<div class="timestamp">' + timestamp + '</div>' + content;
            if (tools && tools.length) {
                html += '<div class="tools">🔧 ' + tools.join(', ') + '</div>';
            }
            div.innerHTML = html;
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function handleKeyPress(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const message = input.value.trim();

            if (!message) return;

            // Afficher le message utilisateur
            renderMessage('user', message, new Date().toLocaleString());
            input.value = '';

            // Afficher le chargement
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant loading';
            chat.appendChild(loadingDiv);

            try {
                // Appel à l'API (l'historique est gardé côté serveur)
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: message}),
                });

                if (!response.ok) throw new Error('Erreur API');

                const data = await response.json();

                // Remplacer le chargement par la vraie réponse
                chat.removeChild(loadingDiv);
                renderMessage('assistant', data.content, new Date().toLocaleString(), data.tools_used);

            } catch (error) {
                chat.removeChild(loadingDiv);
                renderMessage('assistant', '⚠️ Erreur : ' + error.message, new Date().toLocaleString());
            }
        }

        // Initialisation
        renderMessage('assistant', 'Bonjour ! Je suis Hermes, votre assistant personnel. Comment puis-je vous aider ?', new Date().toLocaleString());
    </script>
</body>
</html>
"""


def format_response(result) -> dict[str, Any]:
    """Formate la réponse de l'agent en JSON (contenu + outils utilisés)."""
    return {
        "role": result.message.role,
        "content": result.message.content or "",
        "tools_used": result.tools_used,
        "rounds": result.rounds,
    }


def create_app() -> Flask:
    """Construit l'application Flask (séparé du lancement pour les tests)."""
    app = Flask(__name__)

    @app.route("/")
    def dashboard():
        """Affiche le dashboard web."""
        return render_template_string(DASHBOARD_TEMPLATE)

    @app.route("/api/chat", methods=["POST"])
    def chat_api():
        """Point d'entrée API : un message utilisateur, la réponse de l'agent.

        Accepte {"message": "..."} ou {"messages": [{"role": "user", ...}, ...]}
        (compatibilité avec l'ancien format ; seul le dernier message est utilisé).
        L'historique complet de la conversation est conservé côté serveur.
        """
        sid, history, is_new = _get_session()

        try:
            data = request.get_json(silent=True) or {}

            if isinstance(data.get("message"), str) and data["message"].strip():
                user_content = data["message"].strip()
            elif data.get("messages"):
                user_content = (data["messages"][-1].get("content") or "").strip()
            else:
                user_content = ""

            if not user_content:
                return jsonify({"error": "Paramètre 'message' requis"}), 400

            _store(history, "user", user_content)
            logger.info("Session %s : message reçu (%d messages dans l'historique)", sid[:8], len(history))

            # Boucle agentique complète (outils exécutés, résultats renvoyés au LLM)
            result = run_agent(history, TOOLS)

            _store(history, "assistant", result.message.content or "")
            if result.tools_used:
                logger.info("Session %s : outils appelés : %s", sid[:8], ", ".join(result.tools_used))

            response = jsonify(format_response(result))
            if is_new:
                # Session fraîche : poser le cookie pour les prochains échanges
                response.set_cookie("hermes_session", sid, max_age=SESSION_TTL, httponly=True)
            return response

        except Exception as e:
            logger.exception("Erreur API")
            return jsonify({"error": str(e)}), 500

    return app


def main():
    """Lance l'API Flask."""
    app = create_app()

    port = int(os.getenv("FLASK_PORT", 9191))
    logger.info(f"🚀 Démarrage de l'API Hermes sur le port {port}")
    logger.info(f"📡 Endpoint : http://0.0.0.0:{port}")

    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
