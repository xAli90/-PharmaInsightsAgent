import json

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

ALLOWED_ARGUMENTS = {
    tool["function"]["name"]: set(tool["function"]["parameters"]["properties"]) for tool in TOOLS
}


class AgentError(Exception):
    """An abort by the code; the message is German and meant for the user (D-49, D-50)."""


def run_agent(client, model: str, question: str, max_rounds: int = 3) -> tuple[str, list[dict]]:
    """Answer the question with tool calls; return the answer and the tool results in call order.

    One round is one call of the model (D-16). The last round has no tools, so the model
    can only answer with the data it already has (D-49).
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    results = []
    for _ in range(max_rounds - 1):
        message = ask_model(client, model, messages, with_tools=True)
        if not message.tool_calls:
            return answer_text(message), results
        messages.append(assistant_message(message))
        results += run_tool_calls(message.tool_calls, messages)
    message = ask_model(client, model, messages, with_tools=False)
    return answer_text(message), results


def ask_model(client, model: str, messages: list[dict], with_tools: bool):
    """Call the model once and return its message; API errors and no choices abort (D-49, D-50)."""
    options = {"tools": TOOLS} if with_tools else {}
    try:
        response = client.chat.completions.create(model=model, messages=messages, **options)
    except openai.APIError as err:
        raise AgentError(MODEL_ERROR) from err
    if not response.choices:
        raise AgentError(NO_ANSWER_ERROR)
    return response.choices[0].message


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
