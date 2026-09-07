from capucine.agents.echo import EchoAgent


def test_echo_returns_the_given_args(deps):
    response = EchoAgent().handle("bonjour", deps)

    assert response.text == "bonjour"


def test_echo_with_no_args_returns_a_friendly_placeholder(deps):
    response = EchoAgent().handle("", deps)

    assert response.text == "(rien à répéter)"
