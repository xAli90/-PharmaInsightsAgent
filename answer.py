import re

from agent import review_ids_from

REVIEW_ID_PATTERN = re.compile(r"\bREV-\d{4}\b")

# Lines the code adds below the answer; they stay German for every question (D-52, D-60).
DATA_BASIS_HEADING = "Datenbasis:"
NO_DATA_FETCHED = "Datenbasis: keine Daten abgerufen"
NO_DATA = "keine Daten"
UNFETCHED_ID_WARNING = "Warnhinweis: {review_id} wurde nie abgerufen"
NO_ID_WARNING = "Warnhinweis: Antwort nennt keine review_id"


def strip_bold(text: str) -> str:
    """Remove the bold markers ** the model writes despite the prompt (D-26, D-51)."""
    return text.replace("**", "")


def cited_ids(text: str) -> set[str]:
    """Return the review IDs the answer cites (D-28)."""
    return set(REVIEW_ID_PATTERN.findall(text))


def collect_drugs(results: list[dict]) -> dict[str, dict]:
    """Merge the tool results per drug, in order of first appearance; errors are skipped.

    Each drug maps to the review count of its statistics (None without a statistics call)
    and the IDs of all samples drawn for it.
    """
    drugs = {}
    for result in results:
        if "error" in result:
            continue
        if "drugs" in result:
            for statistics in result["drugs"]:
                drugs.setdefault(statistics["drug"], {"count": None, "ids": set()})
                drugs[statistics["drug"]]["count"] = statistics["count"]
        else:
            drugs.setdefault(result["drug"], {"count": None, "ids": set()})
            drugs[result["drug"]]["ids"] |= review_ids_from(result)
    return drugs


def drug_line(drug: str, count: int | None, ids: set[str]) -> str:
    """Describe the data of one drug; a part without data is left out (D-57)."""
    parts = []
    if count is not None:
        parts.append(f"Statistik über {count} Reviews")
    if ids:
        parts.append(f"Stichprobe {len(ids)} ({', '.join(sorted(ids))})")
    return f"{drug}: {', '.join(parts) or NO_DATA}"


def data_basis(results: list[dict]) -> list[str]:
    """Return one data-basis line per drug, in order of first appearance (D-27, D-57)."""
    drugs = collect_drugs(results)
    return [drug_line(drug, data["count"], data["ids"]) for drug, data in drugs.items()]


def warnings(answer: str, fetched_ids: set[str]) -> list[str]:
    """Warn about cited IDs never fetched and about an answer citing none (D-28, D-51)."""
    cited = cited_ids(answer)
    unfetched = sorted(cited - fetched_ids)
    lines = [UNFETCHED_ID_WARNING.format(review_id=review_id) for review_id in unfetched]
    if fetched_ids and not cited:
        lines.append(NO_ID_WARNING)
    return lines


def data_basis_block(results: list[dict]) -> str:
    """Return the data basis as a heading with one line per drug, or the line for no data."""
    lines = data_basis(results)
    if not lines:
        return NO_DATA_FETCHED
    return "\n".join([DATA_BASIS_HEADING, *lines])


def finish_answer(answer: str, results: list[dict]) -> str:
    """Return the answer without bold, followed by the data basis and any warnings (D-57)."""
    text = strip_bold(answer)
    fetched_ids = set().union(*(review_ids_from(result) for result in results))
    blocks = [text, data_basis_block(results)]
    found_warnings = warnings(text, fetched_ids)
    if found_warnings:
        blocks.append("\n".join(found_warnings))
    return "\n\n".join(blocks)
