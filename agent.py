"""The agent loop: call the model, run the tools it asks for, stop after max_rounds calls.

The plain openai client is passed in, so tests can hand in a fake (D-02, D-36); one round
is one model call (D-16). Mistakes of the model go back to it as error dicts, while an empty
answer, an API error or an unreadable CSV aborts with AgentError (D-49, D-50). run_agent
returns the tool results, so answer.py can build the data basis from them (D-57), and
reports each round to an optional callback for the -v output (D-32).
"""

import json
import time

import openai
import pandas as pd

from prompts import SYSTEM_PROMPT, tool_message
from tools import TOOLS, get_rating_statistics, get_reviews

# Shown to the user when the code aborts (D-49, D-50).
NO_ANSWER_ERROR = "Das Modell hat keine Antwort geliefert"
MODEL_ERROR = "Das Modell ist nicht erreichbar oder hat den Aufruf abgelehnt"
DATA_ERROR = "Die Daten konnten nicht geladen werden"

# Returned to the model as {"error": ...} so it can correct its call (D-50).
INVALID_JSON_ERROR = "Die Argumente sind kein gültiges JSON."
NOT_AN_OBJECT_ERROR = 'Die Argumente müssen ein JSON-Objekt sein, z. B. {"drug": "PHM-101"}.'

TOOL_FUNCTIONS = {"get_reviews": get_reviews, "get_rating_statistics": get_rating_statistics}

# Derived from the TOOLS schema, so the argument check cannot drift from what the model is offered.
ALLOWED_ARGUMENTS = {
    tool["function"]["name"]: set(tool["function"]["parameters"]["properties"]) for tool in TOOLS
}


class AgentError(Exception):
    """An abort by the code; the message is German and meant for the user (D-49, D-50)."""


def run_agent(
    client, model: str, question: str, max_rounds: int = 3, on_round=None
) -> tuple[str, list[dict]]:
    """Answer the question with tool calls; return the answer and the tool results in call order.

    One round is one call of the model (D-16). The last round leaves out tools, since
    LM Studio may ignore tool_choice="none"; the model can then only answer with the data
    it already has (D-49). If on_round is given, it gets a dict after every model call:
    round (from 1), tools as (name, arguments) pairs, tokens_in, tokens_out (None without
    usage) and seconds, the duration of the model call (D-32).
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    results = []
    for round_number in range(1, max_rounds):
        message, call_stats = ask_model(client, model, messages, with_tools=True)
        report_round(on_round, round_number, message.tool_calls or [], call_stats)
        if not message.tool_calls:
            return answer_text(message), results
        messages.append(assistant_message(message))
        results += run_tool_calls(message.tool_calls, messages)
    message, call_stats = ask_model(client, model, messages, with_tools=False)
    # Tool calls in the last round are never run, so the round reports none.
    report_round(on_round, max_rounds, [], call_stats)
    return answer_text(message), results


def ask_model(client, model: str, messages: list[dict], with_tools: bool) -> tuple[object, dict]:
    """Call the model once; return its message and the call's tokens and seconds.

    API errors and a response without choices abort (D-49, D-50). Servers may leave out
    usage, then both token counts are None (D-32).
    """
    options = {"tools": TOOLS} if with_tools else {}
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(model=model, messages=messages, **options)
    except openai.APIError as err:
        raise AgentError(MODEL_ERROR) from err
    seconds = time.perf_counter() - started
    if not response.choices:
        raise AgentError(NO_ANSWER_ERROR)
    usage = getattr(response, "usage", None)
    call_stats = {
        "tokens_in": getattr(usage, "prompt_tokens", None),
        "tokens_out": getattr(usage, "completion_tokens", None),
        "seconds": seconds,
    }
    return response.choices[0].message, call_stats


def report_round(on_round, round_number: int, tool_calls, call_stats: dict) -> None:
    """Pass the round number, its tool calls and the call's stats to on_round, if given (D-32)."""
    if on_round is None:
        return
    tools = [(tool_call.function.name, tool_call.function.arguments) for tool_call in tool_calls]
    on_round({"round": round_number, "tools": tools, **call_stats})


def answer_text(message) -> str:
    """Return the text of the model's answer; an empty answer aborts (D-49)."""
    if message.content is None or not message.content.strip():
        raise AgentError(NO_ANSWER_ERROR)
    return message.content.strip()


def assistant_message(message) -> dict:
    """Turn the model's tool-calling message into a dict for the next round."""
    return {
        "role": "assistant",
        "content": message.content,
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                },
            }
            for tool_call in message.tool_calls
        ],
    }


def run_tool_calls(tool_calls, messages: list[dict]) -> list[dict]:
    """Run each tool call, append its framed result to messages and return the results."""
    results = []
    for tool_call in tool_calls:
        result = call_tool(tool_call.function.name, tool_call.function.arguments)
        results.append(result)
        messages.append(tool_message(tool_call.id, result))
    return results


def call_tool(name: str, arguments: str | None) -> dict:
    """Run one tool; mistakes of the model come back as {"error": ...} (D-50).

    A missing, empty or unparsable CSV is an infrastructure error the model cannot fix,
    so it aborts.
    """
    if name not in TOOL_FUNCTIONS:
        known = ", ".join(TOOL_FUNCTIONS)
        return {"error": f'Unbekanntes Werkzeug "{name}". Verfügbar sind: {known}.'}
    try:
        parsed = json.loads(arguments or "")
    except json.JSONDecodeError:
        return {"error": INVALID_JSON_ERROR}
    if not isinstance(parsed, dict):
        return {"error": NOT_AN_OBJECT_ERROR}
    unknown = sorted(set(parsed) - ALLOWED_ARGUMENTS[name])
    if unknown:
        allowed = ", ".join(f'"{argument}"' for argument in sorted(ALLOWED_ARGUMENTS[name]))
        return {"error": f'Unbekannter Parameter "{unknown[0]}" für {name}. Erlaubt: {allowed}.'}
    try:
        return TOOL_FUNCTIONS[name](**parsed)
    except (OSError, pd.errors.ParserError, pd.errors.EmptyDataError) as err:
        raise AgentError(DATA_ERROR) from err


def review_ids_from(result: dict) -> set[str]:
    """Return the review IDs a tool result handed to the model (D-57)."""
    return {review["review_id"] for review in result.get("reviews", [])}
