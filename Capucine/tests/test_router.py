from capucine.agents.echo import EchoAgent
from capucine.router import Router


def test_route_known_command_returns_the_agent():
    echo_agent = EchoAgent()
    router = Router({"echo": echo_agent})

    assert router.route("echo") is echo_agent


def test_route_unknown_command_returns_none():
    router = Router({"echo": EchoAgent()})

    assert router.route("inconnu") is None
