"""Dashboard web Capucine — tâches, agenda, notes de weekend.

Processus Flask séparé du bot Telegram (capucine/service.py) : chacun ouvre
sa propre connexion SQLite vers le même fichier (cf. capucine/store.py —
volume d'écriture personnel, pas de souci de contention). Lancé avec
`threaded=False` (cf. plan de portage) : Store n'est pas thread-safe
(sqlite3.connect sans check_same_thread=False), donc toutes les requêtes
doivent être traitées séquentiellement dans le même thread que celui qui a
construit le Store.

Pas de login applicatif — accès protégé uniquement par le réseau
(LAN/Tailscale de confiance), même posture que le dashboard Pi Monitor sur
ce Pi. La garde ci-dessous ne vérifie qu'un token Google valide, pas une
identité utilisateur.

Routes :
  GET  /                          → Interface principale (dashboard.html)
  GET  /weekends                  → Page dédiée calendrier des weekends (weekends.html)
  GET  /login, /auth/status,
       /auth/login, /auth/callback → Flux OAuth Google (navigateur)
  GET  /api/tasks                 → Tâches Google Tasks (JSON)
  POST /api/tasks/<id>/complete   → Marque une tâche complétée
  PUT  /api/tasks/<id>            → Modifie titre/échéance d'une tâche
  GET  /api/events                → Événements Google Calendar (JSON)
  GET  /api/weekend-notes         → Notes de weekends {sat_date: note}
  PUT  /api/weekend-notes/<date>  → Enregistre la note d'un weekend
  GET  /api/stats                 → Compteurs résumés (cards du haut)
"""
import os

# Doit être positionné avant l'import de google_auth_oauthlib.flow : HTTP
# simple sur réseau de confiance (pas de TLS local), comme prj-jeffrey.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

import logging
import re
from datetime import date, datetime

import pytz
from flask import Flask, jsonify, redirect, render_template, request, url_for
from google_auth_oauthlib.flow import Flow

from capucine import google_auth
from capucine.cache import TTLCache
from capucine.config import Config, load_config
from capucine.google_calendar import GoogleCalendarClient
from capucine.google_tasks import GoogleTasksClient
from capucine.store import Store

logger = logging.getLogger(__name__)

# Noms français pour l'affichage des dates d'événements. `strftime("%A %d %B")`
# dépend de la locale du système (le Pi tourne en locale C → nom en anglais),
# et forcer locale.setlocale("fr_FR.UTF-8") exigerait que cette locale soit
# installée sur le Pi — une table statique est plus simple et fiable.
_JOURS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_MOIS_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _format_date_fr(d: date) -> str:
    """Formate une date en français, ex. "mercredi 30 septembre"."""
    return f"{_JOURS_FR[d.weekday()]} {d.day:02d} {_MOIS_FR[d.month - 1]}"


def _classify_task_status(due_str: "str | None", today: date, tz) -> "tuple[str, str | None]":
    """Classe une tâche Google Tasks selon son échéance : 'overdue' (passée),
    'today', ou 'upcoming' (future ou sans échéance). Retourne aussi la date
    formatée pour l'affichage, ou None si la tâche n'a pas d'échéance."""
    if not due_str:
        return "upcoming", None
    try:
        # "Z" non supporté par fromisoformat en Python < 3.11.
        due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00")).astimezone(tz)
    except (ValueError, TypeError):
        return "upcoming", None

    due_date = due_dt.date()
    if due_date < today:
        status = "overdue"
    elif due_date == today:
        status = "today"
    else:
        status = "upcoming"
    return status, due_dt.strftime("%d/%m/%Y")


def _enrich_event_for_display(event: dict, today: date, tz) -> dict:
    """Ajoute les champs d'affichage (date/heure formatées, clé de
    regroupement, 'est aujourd'hui') à un événement Google Calendar déjà
    normalisé par GoogleCalendarClient — sans muter l'original."""
    enriched = dict(event)
    start_str = event.get("start") or ""

    if "T" in start_str:
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00")).astimezone(tz)
            enriched["date_display"] = _format_date_fr(start_dt.date())
            enriched["time_display"] = start_dt.strftime("%H:%M")
            enriched["is_today"] = start_dt.date() == today
            enriched["date_key"] = start_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            enriched["date_display"] = start_str[:10]
            enriched["time_display"] = ""
            enriched["is_today"] = False
            enriched["date_key"] = start_str[:10]
    else:
        # Événement journée entière : `start` est déjà une date "YYYY-MM-DD".
        # Formaté comme les événements horodatés (_format_date_fr) pour que
        # l'affichage groupé par jour reste cohérent — sans ça le
        # regroupement mélangeait "mercredi 30 septembre" (événements
        # horodatés) et "2026-10-04" (journée entière) dans la même liste.
        try:
            enriched["date_display"] = _format_date_fr(date.fromisoformat(start_str))
        except (ValueError, TypeError):
            enriched["date_display"] = start_str
        enriched["time_display"] = "Journée"
        enriched["is_today"] = start_str == str(today)
        enriched["date_key"] = start_str

    return enriched


def create_app(
    config: Config,
    calendar: "GoogleCalendarClient | None" = None,
    tasks: "GoogleTasksClient | None" = None,
    store: "Store | None" = None,
) -> Flask:
    """Factory testable : injecter `calendar`/`tasks`/`store` avec des
    doubles de test pour éviter tout appel réseau réel (cf. tests/test_dashboard_routes.py)."""
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.urandom(24)

    calendar = calendar or GoogleCalendarClient(
        credentials_file=config.google_credentials_file,
        token_file=config.google_token_file,
        timezone=config.calendar_timezone,
        extra_calendar_names=config.extra_calendar_names,
    )
    tasks = tasks or GoogleTasksClient(
        credentials_file=config.google_credentials_file,
        token_file=config.google_token_file,
        timezone=config.calendar_timezone,
    )
    store = store or Store(config.db_path)
    tz = pytz.timezone(config.calendar_timezone)
    deployed_at = datetime.now(tz).strftime("%d/%m %H:%M")
    cache = TTLCache(ttl_seconds=config.dashboard_cache_ttl_seconds)

    # Dict mutable (plutôt qu'une variable "global") pour porter l'état
    # OAuth temporaire entre /auth/login et /auth/callback, scopé à cette
    # instance d'app (utile en test où plusieurs create_app() coexistent).
    oauth_state = {"value": None}

    # ─────────────────────────────────────────────────────────────
    # Garde d'authentification Google
    # ─────────────────────────────────────────────────────────────

    @app.before_request
    def require_google_auth():
        if request.path.startswith("/auth") or request.path == "/login":
            return
        if not google_auth.is_credentials_valid(config.google_token_file):
            if request.path.startswith("/api"):
                return jsonify({"error": "auth_required", "login_url": url_for("login_page")}), 401
            return redirect(url_for("login_page", reason="expired"))

    # ─────────────────────────────────────────────────────────────
    # Routes OAuth
    # ─────────────────────────────────────────────────────────────

    @app.route("/login")
    def login_page():
        reason = request.args.get("reason", "missing")
        return render_template("login.html", reason=reason)

    @app.route("/auth/status")
    def auth_status():
        return jsonify({"connected": google_auth.is_credentials_valid(config.google_token_file)})

    @app.route("/auth/login")
    def auth_login():
        flow = Flow.from_client_secrets_file(
            config.google_credentials_file,
            scopes=google_auth.GOOGLE_SCOPES,
            redirect_uri=config.oauth_redirect_uri,
        )
        auth_url, state = flow.authorization_url(
            access_type="offline", prompt="consent", include_granted_scopes="true"
        )
        oauth_state["value"] = state
        return redirect(auth_url)

    @app.route("/auth/callback")
    def auth_callback():
        flow = Flow.from_client_secrets_file(
            config.google_credentials_file,
            scopes=google_auth.GOOGLE_SCOPES,
            redirect_uri=config.oauth_redirect_uri,
            state=oauth_state["value"],
        )
        flow.fetch_token(authorization_response=request.url)
        google_auth.save_token(flow.credentials, config.google_token_file)
        logger.info("[dashboard] Token Google renouvelé via le dashboard.")
        oauth_state["value"] = None
        return redirect("/")

    # ─────────────────────────────────────────────────────────────
    # Page principale
    # ─────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("dashboard.html", deployed_at=deployed_at)

    @app.route("/weekends")
    def weekends_page():
        return render_template("weekends.html", deployed_at=deployed_at)

    # ─────────────────────────────────────────────────────────────
    # API — Tâches
    # ─────────────────────────────────────────────────────────────

    @app.route("/api/tasks")
    def api_tasks():
        max_results = request.args.get("max_results", default=50, type=int)
        try:
            task_list = cache.get_or_set(
                f"tasks:{max_results}",
                lambda: tasks.list_tasks(max_results=max_results, show_completed=False),
            )
        except Exception as e:
            logger.error("[dashboard] Erreur Google Tasks : %s", e)
            return jsonify({"error": str(e)}), 500

        today = datetime.now(tz).date()
        for task in task_list:
            status, due_display = _classify_task_status(task.get("due"), today, tz)
            task["status_label"] = status
            if due_display:
                task["due_display"] = due_display

        return jsonify(task_list)

    @app.route("/api/tasks/<task_id>/complete", methods=["POST"])
    def api_task_complete(task_id):
        try:
            result = tasks.complete_task(task_id)
            cache.invalidate("tasks:")
            cache.invalidate("stats")
            return jsonify({"ok": True, "task": result})
        except Exception as e:
            logger.error("[dashboard] Erreur complete_task %s : %s", task_id, e)
            return jsonify({"error": str(e)}), 500

    @app.route("/api/tasks/<task_id>", methods=["PUT"])
    def api_task_update(task_id):
        data = request.get_json(silent=True) or {}
        title = data.get("title") or None
        due = data.get("due") or None

        if due:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
                return jsonify({"error": "Format de date invalide, attendu YYYY-MM-DD"}), 400
            due = f"{due}T00:00:00"

        try:
            result = tasks.update_task(task_id, title=title, due=due)
            cache.invalidate("tasks:")
            cache.invalidate("stats")
            return jsonify({"ok": True, "task": result})
        except Exception as e:
            logger.error("[dashboard] Erreur update_task %s : %s", task_id, e)
            return jsonify({"error": str(e)}), 500

    # ─────────────────────────────────────────────────────────────
    # API — Événements
    # ─────────────────────────────────────────────────────────────

    @app.route("/api/events")
    def api_events():
        days_ahead = request.args.get("days_ahead", default=30, type=int)
        max_results = request.args.get("max_results", default=50, type=int)
        try:
            events = cache.get_or_set(
                f"events:{days_ahead}:{max_results}",
                lambda: calendar.list_events(days_ahead=days_ahead, max_results=max_results),
            )
        except Exception as e:
            logger.error("[dashboard] Erreur Google Calendar : %s", e)
            return jsonify({"error": str(e)}), 500

        today = datetime.now(tz).date()
        return jsonify([_enrich_event_for_display(e, today, tz) for e in events])

    # ─────────────────────────────────────────────────────────────
    # API — Notes de weekends
    # ─────────────────────────────────────────────────────────────

    @app.route("/api/weekend-notes")
    def api_weekend_notes_get():
        return jsonify(cache.get_or_set("weekend_notes", store.get_all_weekend_notes))

    @app.route("/api/weekend-notes/<sat_date>", methods=["PUT"])
    def api_weekend_notes_put(sat_date):
        """Écrit dans le Store immédiatement (réponse rapide), puis
        synchronise vers Google Calendar (source de vérité) — même ordre
        que prj-jeffrey/dashboard/notes.py::set_note. Un échec de sync
        Google n'annule pas l'écriture Store : elle sera rattrapée à la
        prochaine lecture via GoogleCalendarClient.get_all_weekend_notes."""
        data = request.get_json(silent=True) or {}
        note = str(data.get("note", "")).strip()

        store.set_weekend_note(sat_date, note)
        cache.invalidate("weekend_notes")
        try:
            if note:
                calendar.upsert_weekend_note(sat_date, note)
            else:
                calendar.delete_weekend_note(sat_date)
        except Exception as e:
            logger.warning("[dashboard] Sync Google Calendar weekend %s échouée : %s", sat_date, e)

        return jsonify({"ok": True})

    # ─────────────────────────────────────────────────────────────
    # API — Stats (cards du haut)
    # ─────────────────────────────────────────────────────────────

    @app.route("/api/stats")
    def api_stats():
        now = datetime.now(tz)
        today = now.date()

        overdue_count = today_count = upcoming_count = 0
        tasks_error = None
        try:
            task_list = cache.get_or_set(
                "stats:tasks", lambda: tasks.list_tasks(max_results=100, show_completed=False)
            )
            for task in task_list:
                status, _ = _classify_task_status(task.get("due"), today, tz)
                if status == "overdue":
                    overdue_count += 1
                elif status == "today":
                    today_count += 1
                else:
                    upcoming_count += 1
        except Exception as e:
            tasks_error = str(e)

        today_events_count = 0
        events_error = None
        try:
            event_list = cache.get_or_set(
                "stats:events", lambda: calendar.list_events(days_ahead=1, max_results=20)
            )
            for event in event_list:
                if _enrich_event_for_display(event, today, tz)["is_today"]:
                    today_events_count += 1
        except Exception as e:
            events_error = str(e)

        return jsonify({
            "tasks": {"overdue": overdue_count, "today": today_count, "upcoming": upcoming_count, "error": tasks_error},
            "events": {"today": today_events_count, "error": events_error},
            "updated_at": now.strftime("%d/%m/%Y %H:%M:%S"),
        })

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    config = load_config()
    app = create_app(config)
    logger.info("[dashboard] Démarré sur http://0.0.0.0:%s", config.dashboard_port)
    # threaded=False : Store n'est pas thread-safe (cf. docstring de ce module).
    app.run(host="0.0.0.0", port=config.dashboard_port, debug=False, threaded=False)


if __name__ == "__main__":
    main()
