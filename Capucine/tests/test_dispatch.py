from capucine.dispatch import IncomingMessage, extract_message, handle_message, parse_command
from capucine.router import Router


def test_parse_command_extracts_command_and_args():
    assert parse_command("/echo bonjour") == ("echo", "bonjour")


def test_parse_command_with_no_args():
    assert parse_command("/echo") == ("echo", "")


def test_parse_command_without_leading_slash_has_no_command():
    assert parse_command("bonjour tout le monde") == ("", "bonjour tout le monde")


def test_parse_command_with_newline_before_args():
    # Message Telegram naturel : /synthese puis retour à la ligne puis le
    # texte (ex. un article collé) — le premier espace ne doit pas servir
    # de frontière, seul le premier bloc de whitespace après la commande.
    assert parse_command("/synthese\nceci est un texte à résumer") == (
        "synthese",
        "ceci est un texte à résumer",
    )


def test_extract_message_from_valid_update():
    update = {"update_id": 1, "message": {"chat": {"id": 42}, "text": "/echo bonjour"}}

    message = extract_message(update)

    assert message == IncomingMessage(chat_id=42, text="/echo bonjour")


def test_extract_message_returns_none_when_no_message():
    assert extract_message({"update_id": 1}) is None


def test_extract_message_returns_none_when_message_has_no_text():
    update = {"update_id": 1, "message": {"chat": {"id": 42}, "photo": []}}

    assert extract_message(update) is None


class _StubAgent:
    def __init__(self, text="ok", raises=False):
        self._text = text
        self._raises = raises

    def handle(self, args, deps):
        if self._raises:
            raise RuntimeError("boom")
        from capucine.agents.base import AgentResponse

        return AgentResponse(text=self._text)


def test_handle_message_ignores_messages_from_another_chat_id(deps):
    router = Router({"echo": _StubAgent()})
    message = IncomingMessage(chat_id=999, text="/echo bonjour")

    reply = handle_message(message, router, deps, allowed_chat_id=42)

    assert reply is None


def test_handle_message_routes_known_command_to_its_agent(deps):
    router = Router({"echo": _StubAgent(text="bonjour")})
    message = IncomingMessage(chat_id=42, text="/echo salut")

    reply = handle_message(message, router, deps, allowed_chat_id=42)

    assert reply == "bonjour"


def test_handle_message_on_unknown_command_returns_explicit_error(deps):
    router = Router({})
    message = IncomingMessage(chat_id=42, text="/inconnu")

    reply = handle_message(message, router, deps, allowed_chat_id=42)

    assert reply == "Commande inconnue : /inconnu"


def test_handle_message_on_plain_text_without_slash_is_ignored(deps):
    router = Router({})
    message = IncomingMessage(chat_id=42, text="bonjour")

    reply = handle_message(message, router, deps, allowed_chat_id=42)

    assert reply is None


def test_handle_message_on_agent_error_returns_friendly_message(deps):
    router = Router({"echo": _StubAgent(raises=True)})
    message = IncomingMessage(chat_id=42, text="/echo bonjour")

    reply = handle_message(message, router, deps, allowed_chat_id=42)

    assert reply == "Désolé, /echo a rencontré une erreur."
