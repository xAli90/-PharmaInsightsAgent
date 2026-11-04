"""Load the review CSV and draw the sample of reviews the model reads.

Drug codes are normalized to the form PHM-101 (D-48). The sample takes up to PER_BAND
reviews from each rating band with a fixed seed (D-46, D-56).
"""

import re
from pathlib import Path

import pandas as pd

CSV_PATH = Path(__file__).parent / "data" / "pharma_reviews.csv"

# 12 reviews, 4 per rating band; rule 10 in docs/system-prompt-entwurf.md and the
# limits statement (D-42) rely on "je 4" (D-56).
PER_BAND = 4

# A fixed seed makes the same question read the same sample, so runs are repeatable.
SEED = 42

# Low, middle and high ratings; 4 still counts as low and 7 already as high (D-46).
RATING_BANDS = ((1, 4), (5, 6), (7, 10))

DRUG_CODE_PATTERN = re.compile(r"PHM[- ]?(\d{3})")


def load_reviews(path: Path = CSV_PATH) -> pd.DataFrame:
    """Load the review CSV, stripping the byte order mark from the header."""
    return pd.read_csv(path, encoding="utf-8-sig")


def normalize_drug_code(code: str) -> str:
    """Turn variants like 'phm 101' or 'PHM101' into 'PHM-101'; return others cleaned."""
    cleaned = code.strip().upper()
    match = DRUG_CODE_PATTERN.fullmatch(cleaned)
    if match is None:
        return cleaned
    return f"PHM-{match.group(1)}"


def sample_reviews(reviews: pd.DataFrame, drug: str) -> pd.DataFrame:
    """Draw up to PER_BAND reviews per rating band for one drug, low band first."""
    drug_reviews = reviews[reviews["drug_name"] == normalize_drug_code(drug)]
    band_samples = []
    for low, high in RATING_BANDS:
        band = drug_reviews[drug_reviews["rating"].between(low, high)]
        band_samples.append(band.sample(n=min(PER_BAND, len(band)), random_state=SEED))
    return pd.concat(band_samples)
