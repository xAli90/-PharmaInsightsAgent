"""The two tools the model can call, get_reviews and get_rating_statistics, and their schema.

Each tool returns a plain dict: get_reviews a stratified sample of reviews for one drug
(D-48, D-56), get_rating_statistics statistics over all reviews of one drug or of all
drugs (D-29, D-48). An unknown drug is no error and comes back with the known codes (D-25).
"""

from functools import cache

import pandas as pd

from data import PER_BAND, RATING_BANDS, load_reviews, normalize_drug_code, sample_reviews

# Shown instead of a missing text; "keine Angabe" would read as "no side effects" (D-48).
EMPTY_FIELD = "(leer)"

NOT_A_STRING_ERROR = 'Der Parameter "drug" muss ein Präparat-Code als Text sein, z. B. "PHM-101".'

DRUG_PARAMETER = {"type": "string", "description": "Präparat-Code, z. B. PHM-101"}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_reviews",
            "description": (
                "Liefert eine nach Rating geschichtete Stichprobe von Reviews zu einem "
                "Präparat, je Review mit Rating, Beschwerde, Wirkung, Nebenwirkungen und Kommentar."
            ),
            "parameters": {
                "type": "object",
                "properties": {"drug": DRUG_PARAMETER},
                "required": ["drug"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_rating_statistics",
            "description": (
                "Liefert über alle Reviews je Präparat Anzahl, Rating-Verteilung "
                "(1–4 / 5–6 / 7–10), Durchschnitt und Beschwerden. Ohne drug: alle Präparate."
            ),
            "parameters": {
                "type": "object",
                "properties": {"drug": DRUG_PARAMETER},
                "required": [],
            },
        },
    },
]


# A load that raises is not cached, so the next call tries again.
@cache
def cached_reviews() -> pd.DataFrame:
    """Load the review CSV once and reuse it for every tool call."""
    return load_reviews()


def known_drugs() -> list[str]:
    """Return the sorted drug codes that occur in the data."""
    return sorted(str(code) for code in cached_reviews()["drug_name"].unique())


def count_per_band(ratings: pd.Series) -> dict[str, int]:
    """Count the ratings that fall into each rating band, low band first."""
    return {
        f"{low}–{high}": int(ratings.between(low, high).sum())
        for low, high in RATING_BANDS
    }


def describe_sample(band_counts: dict[str, int], total: int) -> str:
    """Describe a sample, naming the real count per band if one falls short (D-56)."""
    sample_size = sum(band_counts.values())
    if all(count == PER_BAND for count in band_counts.values()):
        bands = " / ".join(band_counts)
        return f"{sample_size} von {total}, je {PER_BAND} aus Rating {bands}"
    parts = ", ".join(f"{count} aus Rating {label}" for label, count in band_counts.items())
    return f"{sample_size} von {total}: {parts}"


def unknown_drug(code: str) -> dict:
    """Answer an unknown drug code with the known codes; this is not an error (D-25, D-50)."""
    return {"found": False, "drug": code, "known_drugs": known_drugs()}


def field_text(value: object) -> str:
    """Return a review text, or EMPTY_FIELD if the value is missing."""
    return EMPTY_FIELD if pd.isna(value) else str(value)


def review_entry(row: pd.Series) -> dict:
    """Turn one CSV row into the review fields the model reads."""
    return {
        "review_id": str(row["review_id"]),
        "rating": int(row["rating"]),
        "condition": field_text(row["condition"]),
        "benefits": field_text(row["benefits_review"]),
        "side_effects": field_text(row["side_effects_review"]),
        "comments": field_text(row["comments_review"]),
    }


def get_reviews(drug: str | None = None) -> dict:
    """Return the stratified sample of reviews for one drug (D-48, D-57).

    drug defaults to None so a call with empty model arguments returns an error dict
    instead of raising (D-50).
    """
    if not isinstance(drug, str):
        return {"error": NOT_A_STRING_ERROR}
    code = normalize_drug_code(drug)
    if code not in known_drugs():
        return unknown_drug(code)
    reviews = cached_reviews()
    sample = sample_reviews(reviews, code)
    total = int((reviews["drug_name"] == code).sum())
    return {
        "found": True,
        "drug": code,
        "sample": describe_sample(count_per_band(sample["rating"]), total),
        "reviews": [review_entry(row) for _, row in sample.iterrows()],
    }


def drug_statistics(code: str) -> dict:
    """Summarize all reviews of one drug: count, rating bands, average, conditions."""
    reviews = cached_reviews()
    drug_reviews = reviews[reviews["drug_name"] == code]
    conditions = drug_reviews["condition"].value_counts()
    return {
        "drug": code,
        "count": len(drug_reviews),
        "bands": count_per_band(drug_reviews["rating"]),
        "average": round(float(drug_reviews["rating"].mean()), 1),
        "conditions": {str(name): int(count) for name, count in conditions.items()},
    }


def get_rating_statistics(drug: str | None = None) -> dict:
    """Return rating statistics over all reviews, for one drug or for all (D-29, D-48)."""
    if drug is None:
        return {"found": True, "drugs": [drug_statistics(code) for code in known_drugs()]}
    if not isinstance(drug, str):
        return {"error": NOT_A_STRING_ERROR}
    code = normalize_drug_code(drug)
    if code not in known_drugs():
        return unknown_drug(code)
    return {"found": True, "drugs": [drug_statistics(code)]}
