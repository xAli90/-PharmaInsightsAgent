"""Tests of the agent loop, with a fake client in place of the model (D-36).

They cover the round limit and the last round without tools (D-16, D-49), errors that go
back to the model versus errors that abort (D-50), the framed tool messages (D-62), the
tool results the loop returns (D-57) and the round reports for -v (D-32).
"""

import json
from types import SimpleNamespace

import openai
import pytest

import tools
from agent import AgentError, call_tool, review_ids_from, run_agent
from data import load_reviews
from prompts import FRAME_CLOSE, FRAME_OPEN
from tools import TOOLS, get_rating_statistics, get_reviews

MODEL = "test-model"
QUESTION = "Wie bewerten Patienten PHM-101?"
CSV_HEADER = (
    "\ufeffreview_id,drug_name,condition,benefits_review,side_effects_review,"
    "comments_review,rating\n"
)


class FakeClient:
    """Stands in for openai.OpenAI: returns prepared responses in order and records calls (D-36).

    A prepared item that is an exception is raised instead of returned.
    """

    def __init__(self, responses: list):
        """Keep the prepared responses and expose them as chat.completions.create."""
        self.responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        """Record the call with a copy of its messages and return the next response."""
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response_with(message: SimpleNamespace) -> SimpleNamespace:
    """Wrap a message the way a chat completion response carries it."""
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def text_response(content: str | None) -> SimpleNamespace:
    """Return a response whose message is a plain text answer."""
    return response_with(SimpleNamespace(content=content, tool_calls=None))


def tool_response(*calls: tuple[str, str]) -> SimpleNamespace:
    """Return a response whose message calls tools, given as (name, arguments) pairs."""
    tool_calls = [
        SimpleNamespace(
            id=f"call_{index}",
            type="function",
            function=SimpleNamespace(name=name, arguments=arguments),
        )
        for index, (name, arguments) in enumerate(calls)
    ]
    return response_with(SimpleNamespace(content=None, tool_calls=tool_calls))


def tool_response_with_text(content: str, *calls: tuple[str, str]) -> SimpleNamespace:
    """Return a response that calls tools and also carries a text answer."""
    response = tool_response(*calls)
    response.choices[0].message.content = content
    return response


def with_usage(response: SimpleNamespace, tokens_in: int, tokens_out: int) -> SimpleNamespace:
    """Add the usage a server reports to a prepared response and return it."""
    response.usage = SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out)
    return response


def tool_results(call: dict) -> list[dict]:
    """Parse the framed tool messages a model call received, in order."""
    results = []
    for message in call["messages"]:
        if message["role"] == "tool":
            content = message["content"]
            assert content.startswith(FRAME_OPEN) and content.endswith(FRAME_CLOSE)
            results.append(json.loads(content[len(FRAME_OPEN) : -len(FRAME_CLOSE)]))
    return results


def error_after_tool_call(name: str, arguments: str) -> dict:
    """Run one faulty tool call followed by an answer and return the tool result the model saw."""
    client = FakeClient([tool_response((name, arguments)), text_response("Antwort")])
    answer, _ = run_agent(client, MODEL, QUESTION)
    assert answer == "Antwort"
    [result] = tool_results(client.calls[1])
    return result


def test_answer_without_tools_takes_one_round():
    """A direct text answer ends the loop after one call, with system prompt and question."""
    client = FakeClient([text_response("Kurzfazit: Keine Daten abgerufen.")])
    answer, results = run_agent(client, MODEL, QUESTION)
    assert answer == "Kurzfazit: Keine Daten abgerufen."
    assert results == []
    [call] = client.calls
    assert call["model"] == MODEL
    assert [message["role"] for message in call["messages"]] == ["system", "user"]
    assert call["messages"][1]["content"] == QUESTION


def test_round_limit_stops_a_model_that_keeps_calling_tools():
    """With max_rounds 3 the model is called exactly 3 times; tool calls in the last are ignored."""
    stats_call = ("get_rating_statistics", '{"drug": "PHM-101"}')
    last = tool_response_with_text("Kurzfazit: Antwort trotz Tool-Aufruf.", stats_call)
    client = FakeClient([tool_response(stats_call), tool_response(stats_call), last])
    answer, _ = run_agent(client, MODEL, QUESTION, max_rounds=3)
    assert answer == "Kurzfazit: Antwort trotz Tool-Aufruf."
    assert len(client.calls) == 3
    assert len(tool_results(client.calls[2])) == 2


def test_last_round_has_no_tools_parameter():
    """Earlier rounds offer TOOLS; the last round omits the parameter entirely (D-49)."""
    stats_call = ("get_rating_statistics", "{}")
    client = FakeClient(
        [tool_response(stats_call), tool_response(stats_call), text_response("Antwort")]
    )
    run_agent(client, MODEL, QUESTION, max_rounds=3)
    assert client.calls[0]["tools"] == TOOLS
    assert client.calls[1]["tools"] == TOOLS
    assert "tools" not in client.calls[2]


@pytest.mark.parametrize("content", [None, "", "  \n "])
def test_empty_answer_aborts(content):
    """No text from the model aborts with the message from D-49."""
    client = FakeClient([text_response(content)])
    with pytest.raises(AgentError, match="Das Modell hat keine Antwort geliefert"):
        run_agent(client, MODEL, QUESTION)


def test_tool_calls_without_text_in_last_round_abort():
    """In the last round only the text counts; tool calls without text abort (D-49)."""
    stats_call = ("get_rating_statistics", "{}")
    client = FakeClient([tool_response(stats_call), tool_response(stats_call)])
    with pytest.raises(AgentError, match="Das Modell hat keine Antwort geliefert"):
        run_agent(client, MODEL, QUESTION, max_rounds=2)


def test_tool_message_is_framed_and_answers_its_call():
    """The tool result goes back framed in the role tool under the id of its call (D-62)."""
    client = FakeClient(
        [tool_response(("get_rating_statistics", '{"drug": "PHM-606"}')), text_response("Antwort")]
    )
    run_agent(client, MODEL, QUESTION)
    assistant, tool = client.calls[1]["messages"][2:]
    assert assistant["role"] == "assistant"
    assert assistant["tool_calls"] == [
        {
            "id": "call_0",
            "type": "function",
            "function": {"name": "get_rating_statistics", "arguments": '{"drug": "PHM-606"}'},
        }
    ]
    assert tool["role"] == "tool"
    assert tool["tool_call_id"] == "call_0"
    assert tool["content"].startswith(FRAME_OPEN)
    assert tool_results(client.calls[1]) == [get_rating_statistics("PHM-606")]


def test_unknown_tool_name_goes_back_as_error():
    """A misspelled tool name returns an error naming the available tools; the loop goes on."""
    result = error_after_tool_call("get_review", '{"drug": "PHM-101"}')
    assert result == {
        "error": 'Unbekanntes Werkzeug "get_review". '
        "Verfügbar sind: get_reviews, get_rating_statistics."
    }


def test_invalid_json_goes_back_as_error():
    """Arguments that are not JSON return an error; the loop goes on."""
    result = error_after_tool_call("get_reviews", '{"drug": "PHM-101"')
    assert result == {"error": "Die Argumente sind kein gültiges JSON."}


def test_missing_arguments_go_back_as_invalid_json():
    """Arguments of None from the server return the JSON error instead of a TypeError."""
    assert call_tool("get_reviews", None) == {"error": "Die Argumente sind kein gültiges JSON."}


def test_json_that_is_no_object_goes_back_as_error():
    """A JSON list instead of an object returns an error; the loop goes on."""
    result = error_after_tool_call("get_reviews", '["PHM-101"]')
    assert result == {
        "error": 'Die Argumente müssen ein JSON-Objekt sein, z. B. {"drug": "PHM-101"}.'
    }


def test_unknown_argument_name_goes_back_as_error():
    """An argument outside the tool schema returns an error instead of a TypeError."""
    result = error_after_tool_call("get_reviews", '{"drug_name": "PHM-101"}')
    assert result == {
        "error": 'Unbekannter Parameter "drug_name" für get_reviews. Erlaubt: "drug".'
    }


def test_missing_drug_goes_back_as_the_tool_error():
    """get_reviews without drug answers with its own error dict (D-50)."""
    result = error_after_tool_call("get_reviews", "{}")
    assert result == get_reviews()
    assert "error" in result


def test_csv_error_aborts(monkeypatch):
    """A missing CSV is an infrastructure error: the code aborts, the model is not asked again."""

    def missing_csv():
        """Fail like pandas does when the CSV file does not exist."""
        raise FileNotFoundError("data/pharma_reviews.csv")

    monkeypatch.setattr(tools, "cached_reviews", missing_csv)
    client = FakeClient(
        [tool_response(("get_reviews", '{"drug": "PHM-101"}')), text_response("Antwort")]
    )
    with pytest.raises(AgentError, match="Die Daten konnten nicht geladen werden"):
        run_agent(client, MODEL, QUESTION)
    assert len(client.calls) == 1


@pytest.fixture
def fresh_review_cache():
    """Empty the CSV cache before and after the test, so no other test sees its data."""
    tools.cached_reviews.cache_clear()
    yield
    tools.cached_reviews.cache_clear()


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("", id="empty"),
        pytest.param(CSV_HEADER + '"REV-0001,PHM-101,Migräne\n', id="unparsable"),
    ],
)
def test_broken_csv_aborts(content, tmp_path, monkeypatch, fresh_review_cache):
    """An empty or unparsable CSV fails in pandas and aborts; the model is not asked again."""
    csv_path = tmp_path / "pharma_reviews.csv"
    csv_path.write_text(content, encoding="utf-8")
    monkeypatch.setattr(tools, "load_reviews", lambda: load_reviews(csv_path))
    client = FakeClient(
        [tool_response(("get_reviews", '{"drug": "PHM-101"}')), text_response("Antwort")]
    )
    with pytest.raises(AgentError, match="Die Daten konnten nicht geladen werden"):
        run_agent(client, MODEL, QUESTION)
    assert len(client.calls) == 1


def model_not_loaded_error() -> openai.NotFoundError:
    """Return the 404 that LM Studio sends when the requested model is not loaded."""
    response = SimpleNamespace(request=None, status_code=404, headers={})
    return openai.NotFoundError("model not loaded", response=response, body=None)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(openai.APIConnectionError(request=None), id="unreachable"),
        pytest.param(model_not_loaded_error(), id="status-404"),
    ],
)
def test_api_error_aborts(error):
    """A connection or status error of the client aborts with a message from the code (D-50)."""
    client = FakeClient([error])
    with pytest.raises(AgentError, match="Das Modell ist nicht erreichbar"):
        run_agent(client, MODEL, QUESTION)


def test_response_without_choices_aborts():
    """A response with an empty choices list aborts like an empty answer (D-49)."""
    client = FakeClient([SimpleNamespace(choices=[])])
    with pytest.raises(AgentError, match="Das Modell hat keine Antwort geliefert"):
        run_agent(client, MODEL, QUESTION)


def test_tool_results_are_returned_in_call_order():
    """The loop returns every result it handed to the model, errors included (D-57)."""
    client = FakeClient(
        [
            tool_response(
                ("get_rating_statistics", '{"drug": "PHM-101"}'),
                ("get_reviews", '{"drug": "PHM-101"}'),
            ),
            tool_response(("get_reviews", "{}")),
            text_response("Antwort"),
        ]
    )
    _, results = run_agent(client, MODEL, QUESTION)
    assert results == [get_rating_statistics("PHM-101"), get_reviews("PHM-101"), get_reviews()]
    assert results == tool_results(client.calls[2])


def test_review_ids_are_collected_from_get_reviews():
    """review_ids_from returns the 12 IDs of the sample handed to the model (D-57)."""
    review_ids = review_ids_from(get_reviews("PHM-101"))
    reviews = load_reviews()
    drug_ids = set(reviews.loc[reviews["drug_name"] == "PHM-101", "review_id"])
    assert len(review_ids) == 12
    assert review_ids <= drug_ids


def test_review_ids_from_results_without_reviews_are_empty():
    """Statistics, unknown drugs and errors carry no reviews, so they add no IDs."""
    assert review_ids_from(get_rating_statistics("PHM-101")) == set()
    assert review_ids_from(get_reviews("PHM-999")) == set()
    assert review_ids_from({"error": "x"}) == set()


def test_call_tool_normalizes_drug_code():
    """call_tool passes the parsed arguments on, so the tool still normalizes the code."""
    assert call_tool("get_reviews", '{"drug": "phm 101"}') == get_reviews("PHM-101")


def test_on_round_reports_tools_and_unknown_tokens():
    """Each model call is reported with its tools; without usage the tokens are None (D-32)."""
    client = FakeClient(
        [tool_response(("get_reviews", '{"drug": "PHM-101"}')), text_response("Antwort")]
    )
    rounds = []
    run_agent(client, MODEL, QUESTION, on_round=rounds.append)
    assert [(info["round"], info["tools"]) for info in rounds] == [
        (1, [("get_reviews", '{"drug": "PHM-101"}')]),
        (2, []),
    ]
    assert all(info["tokens_in"] is None and info["tokens_out"] is None for info in rounds)
    assert all(isinstance(info["seconds"], float) and info["seconds"] >= 0 for info in rounds)


def test_on_round_reports_usage_of_the_server():
    """The token counts come from the usage of the response (D-32)."""
    client = FakeClient([with_usage(text_response("Antwort"), 812, 64)])
    rounds = []
    run_agent(client, MODEL, QUESTION, on_round=rounds.append)
    [info] = rounds
    assert (info["tokens_in"], info["tokens_out"]) == (812, 64)


def test_on_round_reports_no_tools_for_the_last_round():
    """Tool calls in the last round are never run, so that round reports none (D-49)."""
    stats_call = ("get_rating_statistics", '{"drug": "PHM-101"}')
    client = FakeClient([tool_response(stats_call), tool_response_with_text("Antwort", stats_call)])
    rounds = []
    run_agent(client, MODEL, QUESTION, max_rounds=2, on_round=rounds.append)
    assert [(info["round"], info["tools"]) for info in rounds] == [(1, [stats_call]), (2, [])]
