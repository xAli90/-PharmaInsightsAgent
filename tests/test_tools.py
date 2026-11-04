import json

import pandas as pd

from data import load_reviews
from tools import TOOLS, describe_sample, get_rating_statistics, get_reviews, review_entry

KNOWN_DRUGS = ["PHM-101", "PHM-202", "PHM-303", "PHM-404", "PHM-505", "PHM-606"]


def csv_row(review_id: str) -> pd.Series:
    """Return the CSV row of one review, with review_id still among its fields."""
    reviews = load_reviews()
    return reviews[reviews["review_id"] == review_id].iloc[0]


def test_unknown_drug_lists_known_drugs_in_both_tools():
    """PHM-999 is no error: both tools answer found False with the six known codes."""
    for result in [get_reviews("PHM-999"), get_rating_statistics("PHM-999")]:
        assert result["found"] is False
        assert result["drug"] == "PHM-999"
        assert result["known_drugs"] == KNOWN_DRUGS


def test_statistics_of_phm_606_show_two_peaks():
    """PHM-606 has 31 / 5 / 34 ratings in the bands, 70 reviews and an average of 5.6."""
    [stats] = get_rating_statistics("PHM-606")["drugs"]
    assert stats["bands"] == {"1–4": 31, "5–6": 5, "7–10": 34}
    assert stats["count"] == 70
    assert stats["average"] == 5.6
    assert list(stats["conditions"].items()) == [("Ekzem", 51), ("Hautreizungen", 19)]


def test_statistics_of_phm_404():
    """PHM-404 has 25 / 18 / 27 ratings, an average of 5.6 and two sleep conditions.

    A second drug with a different distribution checks the bands beyond PHM-606.
    """
    [stats] = get_rating_statistics("PHM-404")["drugs"]
    assert stats["bands"] == {"1–4": 25, "5–6": 18, "7–10": 27}
    assert stats["count"] == 70
    assert stats["average"] == 5.6
    assert list(stats["conditions"].items()) == [
        ("Einschlafprobleme", 52),
        ("Durchschlafprobleme", 18),
    ]


def test_statistics_without_drug_cover_all_drugs():
    """Without a drug code the statistics list all six drugs with consistent counts."""
    drugs = get_rating_statistics()["drugs"]
    assert [entry["drug"] for entry in drugs] == KNOWN_DRUGS
    for entry in drugs:
        assert sum(entry["bands"].values()) == entry["count"] == 70
        assert 1 <= entry["average"] <= 10
        assert entry["conditions"]


def test_review_entry_shows_missing_side_effects_as_empty():
    """The CSV row REV-0107 has no side effects text, so its entry reads '(leer)'."""
    assert review_entry(csv_row("REV-0107"))["side_effects"] == "(leer)"


def test_review_entry_matches_csv_row():
    """The CSV row REV-0001 carries each field under its own key, independent of the sample."""
    assert review_entry(csv_row("REV-0001")) == {
        "review_id": "REV-0001",
        "rating": 5,
        "condition": "Migräne",
        "benefits": "Meine Kopfschmerzen sind etwas seltener, aber weiterhin störend.",
        "side_effects": "Ich weiß nicht, ob meine Müdigkeit tatsächlich vom Präparat stammt.",
        "comments": "Mir fehlt eine zuverlässige Wirkung, deshalb bleibt meine Bewertung mittelmäßig.",
    }


def test_phm_101_sample_has_twelve_reviews():
    """PHM-101 yields 12 reviews and the line for full bands."""
    result = get_reviews("PHM-101")
    assert len(result["reviews"]) == 12
    assert result["sample"] == "12 von 70, je 4 aus Rating 1–4 / 5–6 / 7–10"


def test_sample_line_names_real_counts_of_a_small_band():
    """A band with fewer reviews shows the real count of each band (D-56)."""
    line = describe_sample({"1–4": 4, "5–6": 3, "7–10": 4}, 50)
    assert line == "11 von 50: 4 aus Rating 1–4, 3 aus Rating 5–6, 4 aus Rating 7–10"


def test_drug_code_variants_give_same_result():
    """'phm 101' returns the same as 'PHM-101' in both tools."""
    assert get_reviews("phm 101") == get_reviews("PHM-101")
    assert get_rating_statistics("phm 101") == get_rating_statistics("PHM-101")


def test_non_string_drug_is_an_error():
    """A missing or non-string drug, as from empty model arguments (D-50), yields an error dict."""
    results = [get_reviews(), get_reviews(None), get_reviews(101), get_rating_statistics(101)]
    for result in results:
        assert list(result) == ["error"]


def test_tools_are_named_and_results_serialize():
    """TOOLS names both tools, and every result can be sent to the model as JSON."""
    names = [tool["function"]["name"] for tool in TOOLS]
    assert names == ["get_reviews", "get_rating_statistics"]
    results = [
        get_reviews("PHM-101"),
        get_reviews("PHM-999"),
        get_reviews(None),
        get_rating_statistics(),
        get_rating_statistics("PHM-999"),
    ]
    for result in results:
        json.dumps(result, allow_nan=False)
