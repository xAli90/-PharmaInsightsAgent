"""Command line of the agent: one question as argument, or an interactive session without one.

The settings come from environment variables, optionally from .env, with defaults in the
code (D-15, D-45); a missing model or a round limit under 2 stops at the start (D-52). The
answer with its data basis goes to stdout, the -v lines, the prompt and errors to stderr;
exit code 0 once the model answers, 1 on an abort by the code (D-30 to D-33).
"""

import argparse
import os
import sys

try:
    # Looks unused, but importing it gives input() line editing and history; without it the
    # arrow keys end up as escape bytes in the question. Not every platform ships it.
    import readline  # noqa: F401
except ImportError:
    pass

import openai
from dotenv import load_dotenv

from agent import AgentError, run_agent
from answer import finish_answer

DEFAULT_BASE_URL = "http://localhost:1234/v1"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_MAX_ROUNDS = 3
MIN_ROUNDS = 2

EXIT_OK = 0
EXIT_ABORT = 1
# The shell convention for a process ended by Ctrl+C (128 + SIGINT).
EXIT_INTERRUPTED = 130

# Texts the user sees stay German (D-60).
DESCRIPTION = "Beantwortet Fragen zu Patienten-Reviews von Präparaten aus der Datenbasis."
QUESTION_HELP = (
    "die Frage an den Agenten; ohne Frage startet der interaktive Modus "
    "(Ende mit exit oder Strg+D)"
)
VERBOSE_HELP = "pro Runde Tools, Tokens und Dauer auf stderr ausgeben"
PROMPT = "Frage> "
EXIT_COMMAND = "exit"
ERROR_LINE = "Fehler: {message}"
MISSING_MODEL_ERROR = "OPENAI_MODEL ist nicht gesetzt"
MAX_ROUNDS_ERROR = "AGENT_MAX_ROUNDS muss eine ganze Zahl ab 2 sein"
ROUND_LINE = "Runde {number}: {tools} | Tokens {tokens} | {seconds:.1f} s"
TOTAL_LINE = "Gesamt: {count} Runden | Tokens {tokens} | {seconds:.1f} s"
NO_TOOLS = "keine Tools"
UNKNOWN_COUNT = "?"


def main(argv: list[str] | None = None, client=None) -> int:
    """Run the command line and return the exit code; tests pass a fake client (D-36)."""
    args = parse_args(argv)
    load_dotenv()
    try:
        config = read_config(os.environ)
    except ValueError as err:
        print_error(err)
        return EXIT_ABORT
    if client is None:
        client = openai.OpenAI(base_url=config["base_url"], api_key=config["api_key"])
    try:
        if args.question is None:
            return interactive_session(client, config, args.verbose)
        return single_question(client, config, args.question, args.verbose)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return EXIT_INTERRUPTED


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the arguments; wrong ones end the program with argparse's exit code 2 (D-30)."""
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("question", nargs="?", metavar="frage", help=QUESTION_HELP)
    parser.add_argument("-v", "--verbose", action="store_true", help=VERBOSE_HELP)
    return parser.parse_args(argv)


def read_config(environ) -> dict:
    """Read the settings; a missing model or a bad round limit raises ValueError (D-15, D-52)."""
    model = env_value(environ, "OPENAI_MODEL")
    if model is None:
        raise ValueError(MISSING_MODEL_ERROR)
    max_rounds = env_value(environ, "AGENT_MAX_ROUNDS")
    return {
        "base_url": env_value(environ, "OPENAI_BASE_URL") or DEFAULT_BASE_URL,
        "api_key": env_value(environ, "OPENAI_API_KEY") or DEFAULT_API_KEY,
        "model": model,
        "max_rounds": DEFAULT_MAX_ROUNDS if max_rounds is None else parse_max_rounds(max_rounds),
    }


def env_value(environ, name: str) -> str | None:
    """Return the stripped value of a variable; an empty one counts as unset, like in .env."""
    return environ.get(name, "").strip() or None


def parse_max_rounds(value: str) -> int:
    """Return the round limit; with fewer than 2 rounds no tool could ever be called (D-52)."""
    try:
        max_rounds = int(value)
    except ValueError:
        raise ValueError(MAX_ROUNDS_ERROR) from None
    if max_rounds < MIN_ROUNDS:
        raise ValueError(MAX_ROUNDS_ERROR)
    return max_rounds


def single_question(client, config: dict, question: str, verbose: bool) -> int:
    """Answer one question; an abort by the code gives exit code 1 (D-33)."""
    try:
        answer_question(client, config, question, verbose)
    except AgentError as err:
        print_error(err)
        return EXIT_ABORT
    return EXIT_OK


def interactive_session(client, config: dict, verbose: bool) -> int:
    """Answer questions until exit or Ctrl+D; an abort ends only the current question (D-30)."""
    while True:
        # The prompt goes to stderr like everything that is not answer or data basis (D-33).
        print(PROMPT, end="", file=sys.stderr, flush=True)
        try:
            question = input().strip()
        except EOFError:
            print(file=sys.stderr)
            return EXIT_OK
        if question == EXIT_COMMAND:
            return EXIT_OK
        if not question:
            continue
        try:
            answer_question(client, config, question, verbose)
        except AgentError as err:
            print_error(err)


def answer_question(client, config: dict, question: str, verbose: bool) -> None:
    """Answer one question from scratch and print it with its data basis (D-31, D-57).

    With verbose, each round is printed to stderr as it ends and a total line follows.
    """
    rounds = []

    def print_round(round_info: dict) -> None:
        """Print the line of one round to stderr and keep the round for the total (D-32)."""
        rounds.append(round_info)
        print(round_line(round_info), file=sys.stderr)

    answer, results = run_agent(
        client,
        config["model"],
        question,
        config["max_rounds"],
        on_round=print_round if verbose else None,
    )
    if verbose:
        print(total_line(rounds), file=sys.stderr)
    # Without flush a piped stdout would show the answer only after the next prompt.
    print(finish_answer(answer, results), flush=True)


def round_line(round_info: dict) -> str:
    """Describe one round: tools with their raw arguments, tokens in/out and seconds (D-32)."""
    tools = ", ".join(f"{name}({arguments or ''})" for name, arguments in round_info["tools"])
    return ROUND_LINE.format(
        number=round_info["round"],
        tools=tools or NO_TOOLS,
        tokens=tokens_text(round_info["tokens_in"], round_info["tokens_out"]),
        seconds=round_info["seconds"],
    )


def total_line(rounds: list[dict]) -> str:
    """Sum up the rounds of one question; a token total is unknown if any round lacks it."""
    return TOTAL_LINE.format(
        count=len(rounds),
        tokens=tokens_text(token_total(rounds, "tokens_in"), token_total(rounds, "tokens_out")),
        seconds=sum(round_info["seconds"] for round_info in rounds),
    )


def token_total(rounds: list[dict], key: str) -> int | None:
    """Return the sum of one token count over the rounds, or None if any is unknown."""
    counts = [round_info[key] for round_info in rounds]
    if None in counts:
        return None
    return sum(counts)


def tokens_text(tokens_in: int | None, tokens_out: int | None) -> str:
    """Return the tokens as in/out, with ? for a count the server did not report."""
    counts = (tokens_in, tokens_out)
    return "/".join(UNKNOWN_COUNT if count is None else str(count) for count in counts)


def print_error(message) -> None:
    """Print an error for the user to stderr (D-33)."""
    print(ERROR_LINE.format(message=message), file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
