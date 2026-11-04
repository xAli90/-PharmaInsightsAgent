"""Tests of loading the CSV, normalizing drug codes (D-48) and drawing the sample.

The sample checks use PHM-101 from the CSV and small built tables: 4 reviews per band,
the same IDs on every call, all reviews of a small band and the band edges (D-46, D-56).
"""

import pandas as pd

from data import load_reviews, normalize_drug_code, sample_reviews


def band_counts(sample):
    """Count sampled reviews in the low, middle and high rating band.

    The band limits are written out on purpose, so a wrong RATING_BANDS shows up.
    """
    return [
        int(sample["rating"].between(1, 4).sum()),
        int(sample["rating"].between(5, 6).sum()),
        int(sample["rating"].between(7, 10).sum()),
    ]


def make_reviews(ratings):
    """Build PHM-101 reviews with the given ratings and numbered review IDs."""
    return pd.DataFrame(
        {
            "review_id": [f"R{i:03d}" for i in range(len(ratings))],
            "drug_name": "PHM-101",
            "rating": ratings,
        }
    )


def test_load_reviews_reads_all_rows_without_bom():
    """The CSV loads with all 420 rows and a clean first column name."""
    reviews = load_reviews()
    assert len(reviews) == 420
    assert reviews.columns[0] == "review_id"


def test_normalize_drug_code_variants():
    """Common spellings of a drug code map to the canonical form."""
    for variant in ["phm-101", "PHM 101", "PHM101", " PHM-101 "]:
        assert normalize_drug_code(variant) == "PHM-101"


def test_sample_takes_four_per_band():
    """PHM-101 yields 4 reviews from each rating band, 12 in total."""
    sample = sample_reviews(load_reviews(), "PHM-101")
    assert band_counts(sample) == [4, 4, 4]
    assert len(sample) == 12
    assert (sample["drug_name"] == "PHM-101").all()


def test_sample_is_repeatable():
    """Two calls return the same review IDs in the same order."""
    reviews = load_reviews()
    first = sample_reviews(reviews, "PHM-101")["review_id"].tolist()
    second = sample_reviews(reviews, "PHM-101")["review_id"].tolist()
    assert first == second


def test_sample_takes_all_reviews_of_a_small_band():
    """A band with fewer than 4 reviews contributes all of them."""
    reviews = make_reviews([1, 2, 3, 4, 2, 3] + [5, 6] + [7, 8, 9, 10, 8, 9])
    sample = sample_reviews(reviews, "PHM-101")
    assert band_counts(sample) == [4, 2, 4]


def test_sample_band_edges_are_four_and_seven():
    """Rating 4 belongs to the low band and 7 to the high band."""
    low_edge = sample_reviews(make_reviews([4] * 5 + [5] * 5), "PHM-101")
    assert band_counts(low_edge) == [4, 4, 0]
    high_edge = sample_reviews(make_reviews([6] * 5 + [7] * 5), "PHM-101")
    assert band_counts(high_edge) == [0, 4, 4]


def test_sample_puts_low_band_first():
    """The sample lists the low band first, then the middle and the high band."""
    sample = sample_reviews(make_reviews([7] * 4 + [5] * 4 + [1] * 4), "PHM-101")
    assert sample["rating"].tolist() == [1] * 4 + [5] * 4 + [7] * 4


def test_sample_of_unknown_drug_is_empty():
    """An unknown drug code yields an empty sample with the same columns."""
    reviews = load_reviews()
    sample = sample_reviews(reviews, "PHM-999")
    assert sample.empty
    assert list(sample.columns) == list(reviews.columns)
