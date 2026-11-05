"""Tests of the command line, with the fake client in place of the model (D-36).

They cover the exit codes (D-33, D-49, D-50), the checks of OPENAI_MODEL and
AGENT_MAX_ROUNDS at the start (D-15, D-52), stdout versus stderr, the -v lines (D-32)
and the interactive mode with a fresh start per question (D-30, D-31).
"""

import io
import re
from types import SimpleNamespace

import pytest

import main as cli
from answer import finish_answer
from test_agent import (
    MODEL,
    QUESTION,
    FakeClient,
    model_not_loaded_error,
    text_response,
    tool_response,
    tool_response_with_text,
    with_usage,
)
from tools import get_reviews

REVIEWS_CALL = ("get_reviews", '{"drug": "PHM-101"}')
SECONDS = r"\d+\.\d s"


@pytest.fixture(autouse=True)
def environment(monkeypatch):
    """Set only OPENAI_MODEL, so neither a real .env nor the shell changes a test (D-45)."""
    monkeypatch.setattr(cli, "load_dotenv", lambda: None)
    for name in ("OPENAI_BASE_URL", "OPENAI_API_KEY", "AGENT_MAX_ROUNDS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_MODEL", MODEL)


def cited_answer() -> str:
    """Return an answer that cites a real ID from the PHM-101 sample."""
    review_id = get_reviews("PHM-101")["reviews"][0]["review_id"]
    return f"Kurzfazit: Patienten bewerten PHM-101 gemischt ({review_id})."


def answering_client() -> FakeClient:
    """Return a client that fetches PHM-101 reviews and then answers."""
    return FakeClient([tool_response(REVIEWS_CALL), text_response(cited_answer())])


def interrupt(*args, **kwargs):
    """Raise what Python raises on Ctrl+C."""
    raise KeyboardInterrupt


def set_stdin(monkeypatch, text: str) -> None:
    """Feed the interactive mode the given lines."""
    monkeypatch.setattr("sys.stdin", io.StringIO(text))


def test_single_question_prints_answer_and_data_basis(capsys):
    """One question: answer and data basis on stdout, nothing on stderr, exit 0 (D-33)."""
    client = answering_client()
    assert cli.main([QUESTION], client=client) == 0
    out, err = capsys.readouterr()
    assert out == finish_answer(cited_answer(), [get_reviews("PHM-101")]) + "\n"
    assert "Datenbasis:" in out
    assert err == ""
    assert client.calls[0]["model"] == MODEL
    assert client.calls[0]["messages"][1]["content"] == QUESTION


def test_unknown_drug_ends_with_exit_0(capsys):
    """An unknown drug is no error: the model answers, exit 0 (D-33, D-50)."""
    client = FakeClient(
        [
            tool_response(("get_reviews", '{"drug": "PHM-999"}')),
            text_response("Kurzfazit: Zu PHM-999 liegen keine Daten vor."),
        ]
    )
    assert cli.main(["Wie wirkt PHM-999?"], client=client) == 0
    out, _ = capsys.readouterr()
    assert "PHM-999: keine Daten" in out


def test_model_error_ends_with_exit_1(capsys):
    """An unreachable model aborts: message on stderr, nothing on stdout, exit 1 (D-50)."""
    client = FakeClient([model_not_loaded_error()])
    assert cli.main([QUESTION], client=client) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "Fehler: Das Modell ist nicht erreichbar oder hat den Aufruf abgelehnt\n"


@pytest.mark.parametrize("value", ["1", "0", "-3", "abc", "2.5"])
def test_bad_max_rounds_stops_before_any_model_call(value, monkeypatch, capsys):
    """AGENT_MAX_ROUNDS under 2 or not an integer stops at the start with exit 1 (D-52)."""
    monkeypatch.setenv("AGENT_MAX_ROUNDS", value)
    client = FakeClient([])
    assert cli.main([QUESTION], client=client) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "Fehler: AGENT_MAX_ROUNDS muss eine ganze Zahl ab 2 sein\n"
    assert client.calls == []


@pytest.mark.parametrize("value", [None, "", "  "])
def test_missing_model_stops_before_any_model_call(value, monkeypatch, capsys):
    """Without OPENAI_MODEL there is nothing to call: exit 1 at the start (D-15)."""
    if value is None:
        monkeypatch.delenv("OPENAI_MODEL")
    else:
        monkeypatch.setenv("OPENAI_MODEL", value)
    client = FakeClient([])
    assert cli.main([QUESTION], client=client) == 1
    _, err = capsys.readouterr()
    assert err == "Fehler: OPENAI_MODEL ist nicht gesetzt\n"
    assert client.calls == []


def test_settings_from_dotenv_are_used(monkeypatch):
    """main reads .env before the settings, so a model set only there is called (D-45)."""
    monkeypatch.delenv("OPENAI_MODEL")

    def load_dotenv():
        """Set the model the way a .env file next to main.py would."""
        monkeypatch.setenv("OPENAI_MODEL", "model-from-dotenv")

    monkeypatch.setattr(cli, "load_dotenv", load_dotenv)
    client = FakeClient([text_response("Antwort")])
    assert cli.main([QUESTION], client=client) == 0
    assert client.calls[0]["model"] == "model-from-dotenv"


def test_defaults_for_base_url_and_api_key():
    """Without OPENAI_BASE_URL and OPENAI_API_KEY the LM Studio defaults apply (D-15)."""
    config = cli.read_config({"OPENAI_MODEL": MODEL, "OPENAI_BASE_URL": "  "})
    assert config == {
        "base_url": "http://localhost:1234/v1",
        "api_key": "lm-studio",
        "model": MODEL,
        "max_rounds": 3,
    }


def test_max_rounds_from_the_environment_is_used(monkeypatch, capsys):
    """With AGENT_MAX_ROUNDS=2 the second call is already the last one, without tools (D-16)."""
    monkeypatch.setenv("AGENT_MAX_ROUNDS", "2")
    last = tool_response_with_text(cited_answer(), REVIEWS_CALL)
    client = FakeClient([tool_response(REVIEWS_CALL), last])
    assert cli.main([QUESTION], client=client) == 0
    assert len(client.calls) == 2
    assert "tools" not in client.calls[1]


def test_verbose_prints_rounds_and_total_to_stderr(capsys):
    """-v adds one line per round and a total on stderr; stdout stays the same (D-32)."""
    assert cli.main([QUESTION], client=answering_client()) == 0
    plain_out, _ = capsys.readouterr()
    client = FakeClient(
        [
            with_usage(tool_response(REVIEWS_CALL), 812, 64),
            with_usage(text_response(cited_answer()), 838, 146),
        ]
    )
    assert cli.main(["-v", QUESTION], client=client) == 0
    out, err = capsys.readouterr()
    assert out == plain_out
    lines = err.splitlines()
    assert len(lines) == 3
    assert re.fullmatch(
        r'Runde 1: get_reviews\(\{"drug": "PHM-101"\}\) \| Tokens 812/64 \| ' + SECONDS, lines[0]
    )
    assert re.fullmatch(r"Runde 2: keine Tools \| Tokens 838/146 \| " + SECONDS, lines[1])
    assert re.fullmatch(r"Gesamt: 2 Runden \| Tokens 1650/210 \| " + SECONDS, lines[2])


def test_verbose_without_usage_shows_question_marks(capsys):
    """A server without usage gives ? per round and in the total (D-32)."""
    client = FakeClient(
        [
            tool_response(REVIEWS_CALL, ("get_rating_statistics", '{"drug": "PHM-101"}')),
            with_usage(text_response(cited_answer()), 838, 146),
        ]
    )
    assert cli.main(["--verbose", QUESTION], client=client) == 0
    _, err = capsys.readouterr()
    lines = err.splitlines()
    assert lines[0].startswith(
        'Runde 1: get_reviews({"drug": "PHM-101"}), '
        'get_rating_statistics({"drug": "PHM-101"}) | Tokens ?/? | '
    )
    assert re.fullmatch(r"Gesamt: 2 Runden \| Tokens \?/\? \| " + SECONDS, lines[2])


def test_interactive_answers_each_question_until_exit(monkeypatch, capsys):
    """Two questions, then exit: two answers, each from a fresh start, exit 0 (D-30, D-31)."""
    set_stdin(monkeypatch, "Frage eins\n\nFrage zwei\n exit \nFrage drei\n")
    client = FakeClient([text_response("Antwort eins"), text_response("Antwort zwei")])
    assert cli.main([], client=client) == 0
    out, err = capsys.readouterr()
    answers = [finish_answer("Antwort eins", []), finish_answer("Antwort zwei", [])]
    assert out == "\n".join(answers) + "\n"
    assert err == "Frage> " * 4
    assert [call["messages"][1:] for call in client.calls] == [
        [{"role": "user", "content": "Frage eins"}],
        [{"role": "user", "content": "Frage zwei"}],
    ]


def test_interactive_ends_on_end_of_input(monkeypatch, capsys):
    """Ctrl+D, that is the end of the input, ends the session with exit 0 (D-30)."""
    set_stdin(monkeypatch, "Frage eins\n")
    client = FakeClient([text_response("Antwort eins")])
    assert cli.main([], client=client) == 0
    out, _ = capsys.readouterr()
    assert out == finish_answer("Antwort eins", []) + "\n"


def test_interactive_abort_ends_only_the_question(monkeypatch, capsys):
    """An abort by the code prints the error; the next question is still answered, exit 0."""
    set_stdin(monkeypatch, "Frage eins\nFrage zwei\nexit\n")
    client = FakeClient([model_not_loaded_error(), text_response("Antwort zwei")])
    assert cli.main([], client=client) == 0
    out, err = capsys.readouterr()
    assert out == finish_answer("Antwort zwei", []) + "\n"
    assert "Fehler: Das Modell ist nicht erreichbar" in err


def test_ctrl_c_during_a_question_ends_with_exit_130(capsys):
    """Ctrl+C during a model call ends quietly with exit 130 (D-33)."""
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=interrupt)))
    assert cli.main([QUESTION], client=client) == 130
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "\n"


def test_ctrl_c_at_the_prompt_ends_with_exit_130(monkeypatch, capsys):
    """Ctrl+C while waiting for a question ends the session with exit 130 (D-33)."""
    monkeypatch.setattr("sys.stdin", SimpleNamespace(readline=interrupt))
    assert cli.main([], client=FakeClient([])) == 130


def test_help_is_german_and_ends_with_exit_0(capsys):
    """--help shows the German help texts and exits with 0 (D-30, D-60)."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--help"])
    assert exit_info.value.code == 0
    out, _ = capsys.readouterr()
    assert "Beantwortet Fragen zu Patienten-Reviews" in out
    assert "pro Runde Tools, Tokens und Dauer" in out


def test_unknown_option_ends_with_argparse_exit_2(capsys):
    """Wrong arguments are argparse's case, with its exit code 2 (D-33)."""
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["--unbekannt"])
    assert exit_info.value.code == 2
