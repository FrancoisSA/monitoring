from capucine.agents.aide import AideAgent


def test_aide_lists_every_command():
    response = AideAgent().handle("", None)

    for command in ("/echo", "/synthese", "/presse", "/renault", "/ia", "/agenda"):
        assert command in response.text
