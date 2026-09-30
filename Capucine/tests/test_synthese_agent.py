from capucine.agents.synthese import SyntheseAgent


def test_synthese_returns_the_llm_response(deps, fake_llm):
    fake_llm.response_text = "Voici le résumé."

    response = SyntheseAgent().handle("un long texte à résumer", deps)

    assert response.text == "Voici le résumé."


def test_synthese_includes_the_text_in_the_prompt(deps, fake_llm):
    SyntheseAgent().handle("un texte bien précis", deps)

    assert "un texte bien précis" in fake_llm.calls[0]


def test_synthese_with_empty_args_does_not_call_the_llm(deps, fake_llm):
    response = SyntheseAgent().handle("   ", deps)

    assert fake_llm.calls == []
    assert "texte à résumer" in response.text
