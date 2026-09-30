from capucine.agents.agenda import AgendaAgent
from capucine.llm.base import ToolCall, ToolCallResponse


class FakeCalendar:
    timezone = "Europe/Paris"

    def __init__(self):
        self.calls = []

    def add_event(self, **kwargs):
        self.calls.append(("add_event", kwargs))
        return {"id": "evt-1", "summary": kwargs["summary"], "start": kwargs["start"],
                "end": kwargs.get("end"), "description": "", "location": ""}

    def list_events(self, **kwargs):
        self.calls.append(("list_events", kwargs))
        return []

    def update_event(self, **kwargs):
        self.calls.append(("update_event", kwargs))
        return {}

    def delete_event(self, **kwargs):
        self.calls.append(("delete_event", kwargs))
        return True

    def search_events(self, **kwargs):
        self.calls.append(("search_events", kwargs))
        return []


class FakeTasks:
    def __init__(self):
        self.calls = []

    def add_task(self, **kwargs):
        self.calls.append(("add_task", kwargs))
        return {"id": "task-1", "title": kwargs["title"], "due": kwargs.get("due")}

    def list_tasks(self, **kwargs):
        self.calls.append(("list_tasks", kwargs))
        return []

    def complete_task(self, **kwargs):
        self.calls.append(("complete_task", kwargs))
        return {"id": kwargs["task_id"], "status": "completed"}

    def search_tasks(self, **kwargs):
        self.calls.append(("search_tasks", kwargs))
        return []


class FakeToolCallingLLMClient:
    """Double de test : rejoue une séquence fixe de réponses, un tour à la
    fois — imite le comportement d'un modèle qui appelle des outils puis
    conclut."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append(list(messages))
        return self._responses.pop(0)


def test_agenda_agent_calls_add_event_tool_and_returns_final_text(deps):
    calendar = FakeCalendar()
    llm = FakeToolCallingLLMClient([
        ToolCallResponse(text=None, tool_calls=[
            ToolCall(id="call_1", name="add_event", arguments={"summary": "Déjeuner", "start": "2025-06-10T12:00:00"}),
        ]),
        ToolCallResponse(text="Rendez-vous ajouté pour le 10 juin à midi.", tool_calls=[]),
    ])
    agent = AgendaAgent(calendar=calendar, llm_client=llm)

    response = agent.handle("ajoute un déjeuner demain midi", deps)

    assert response.text == "Rendez-vous ajouté pour le 10 juin à midi."
    assert calendar.calls == [("add_event", {"summary": "Déjeuner", "start": "2025-06-10T12:00:00"})]


def test_agenda_agent_returns_direct_text_without_tool_calls(deps):
    calendar = FakeCalendar()
    llm = FakeToolCallingLLMClient([ToolCallResponse(text="Je ne peux pas faire ça.", tool_calls=[])])
    agent = AgendaAgent(calendar=calendar, llm_client=llm)

    response = agent.handle("fais le café", deps)

    assert response.text == "Je ne peux pas faire ça."
    assert calendar.calls == []


def test_agenda_agent_returns_prompt_for_empty_args(deps):
    agent = AgendaAgent(calendar=FakeCalendar(), llm_client=FakeToolCallingLLMClient([]))

    response = agent.handle("", deps)

    assert "Dites-moi" in response.text


def test_agenda_agent_handles_unknown_tool_gracefully(deps):
    calendar = FakeCalendar()
    llm = FakeToolCallingLLMClient([
        ToolCallResponse(text=None, tool_calls=[ToolCall(id="call_1", name="outil_inexistant", arguments={})]),
        ToolCallResponse(text="D'accord.", tool_calls=[]),
    ])
    agent = AgendaAgent(calendar=calendar, llm_client=llm)

    response = agent.handle("fais un truc bizarre", deps)

    assert response.text == "D'accord."
    second_call_messages = llm.calls[1]
    tool_messages = [m for m in second_call_messages if m.role == "tool"]
    assert "Outil inconnu" in tool_messages[-1].content


def test_agenda_agent_calls_add_task_tool_and_returns_final_text(deps):
    tasks = FakeTasks()
    llm = FakeToolCallingLLMClient([
        ToolCallResponse(text=None, tool_calls=[
            ToolCall(id="call_1", name="add_task", arguments={"title": "Acheter du pain"}),
        ]),
        ToolCallResponse(text="Tâche ajoutée.", tool_calls=[]),
    ])
    agent = AgendaAgent(calendar=FakeCalendar(), llm_client=llm, tasks=tasks)

    response = agent.handle("ajoute une tâche acheter du pain", deps)

    assert response.text == "Tâche ajoutée."
    assert tasks.calls == [("add_task", {"title": "Acheter du pain"})]


def test_agenda_agent_without_tasks_client_reports_unknown_tool(deps):
    """Rétrocompatibilité : un AgendaAgent construit sans `tasks` (comme
    avant l'ajout des tools Tasks) doit dégrader proprement plutôt que
    planter si le modèle tente quand même d'appeler add_task."""
    llm = FakeToolCallingLLMClient([
        ToolCallResponse(text=None, tool_calls=[
            ToolCall(id="call_1", name="add_task", arguments={"title": "Acheter du pain"}),
        ]),
        ToolCallResponse(text="D'accord.", tool_calls=[]),
    ])
    agent = AgendaAgent(calendar=FakeCalendar(), llm_client=llm)

    response = agent.handle("ajoute une tâche", deps)

    assert response.text == "D'accord."
    tool_messages = [m for m in llm.calls[1] if m.role == "tool"]
    assert "Outil inconnu" in tool_messages[-1].content


def test_agenda_agent_stops_after_max_rounds(deps):
    calendar = FakeCalendar()
    always_tool_call = ToolCallResponse(
        text=None, tool_calls=[ToolCall(id="call_1", name="list_events", arguments={})]
    )
    llm = FakeToolCallingLLMClient([always_tool_call] * 10)
    agent = AgendaAgent(calendar=calendar, llm_client=llm)

    response = agent.handle("boucle infinie", deps)

    assert "pas pu terminer" in response.text
