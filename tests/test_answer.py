"""Tests of the post-processing in answer.py, with real sample IDs from the CSV.

They cover the data basis per drug (D-27, D-57), the ID check with word boundaries
(D-28), the warning for an answer without ID and the removal of ** (D-51).
"""

from agent import run_agent
from answer import cited_ids, data_basis, finish_answer, strip_bold, warnings
from data import load_reviews
from test_agent import MODEL, FakeClient, text_response, tool_response
from tools import get_rating_statistics, get_reviews, unknown_drug


def sample_ids(drug: str) -> list[str]:
    """Return the sorted review IDs of the sample get_reviews hands to the model."""
    return sorted(review["review_id"] for review in get_reviews(drug)["reviews"])


def unfetched_id(drug: str) -> str:
    """Return a real review ID of the drug that is not in its sample."""
    reviews = load_reviews()
    drug_ids = set(reviews.loc[reviews["drug_name"] == drug, "review_id"])
    return sorted(drug_ids - set(sample_ids(drug)))[0]


def sample_part(drug: str) -> str:
    """Return the sample part of a data-basis line for the drug's full sample."""
    ids = sample_ids(drug)
    return f"Stichprobe {len(ids)} ({', '.join(ids)})"


def test_cited_ids_finds_every_review_id():
    """All REV-xxxx in the answer count, wherever they stand (D-28)."""
    answer = "Müdigkeit (REV-0001), Schwindel (REV-0002, REV-0417)."
    assert cited_ids(answer) == {"REV-0001", "REV-0002", "REV-0417"}


def test_cited_ids_match_ids_before_punctuation():
    """IDs in brackets and before a full stop or comma are citations."""
    assert cited_ids("Wirkt (REV-0001).") == {"REV-0001"}
    assert cited_ids("Siehe REV-0001.") == {"REV-0001"}
    assert cited_ids("Siehe REV-0001, REV-0107") == {"REV-0001", "REV-0107"}


def test_cited_ids_ignore_ids_inside_longer_words():
    """XREV-0001 and REV-00011 are no citations of REV-0001."""
    assert cited_ids("Siehe XREV-0001 und REV-00011.") == set()


def test_longer_id_does_not_pass_as_fetched_id():
    """REV-00011 must not count as the fetched REV-0001, so the answer cites no ID (D-51)."""
    fetched_ids = set(sample_ids("PHM-101"))
    assert "REV-0001" in fetched_ids
    assert warnings("Negativ: Müdigkeit (REV-00011).", fetched_ids) == [
        "Warnhinweis: Antwort nennt keine review_id"
    ]


def test_invented_id_is_warned():
    """An ID that does not exist in the data was never fetched, so it gets a warning (D-28)."""
    [cited, *_] = sample_ids("PHM-101")
    answer = f"Positiv: Kopfschmerzen seltener ({cited}). Negativ: Übelkeit (REV-0999)."
    assert warnings(answer, set(sample_ids("PHM-101"))) == [
        "Warnhinweis: REV-0999 wurde nie abgerufen"
    ]


def test_real_but_unfetched_id_is_warned():
    """A real ID of the same drug outside the sample was never handed to the model (D-28)."""
    review_id = unfetched_id("PHM-101")
    answer = f"Negativ: Müdigkeit ({review_id})."
    assert warnings(answer, set(sample_ids("PHM-101"))) == [
        f"Warnhinweis: {review_id} wurde nie abgerufen"
    ]


def test_unfetched_ids_are_warned_in_sorted_order():
    """Several unfetched IDs give one warning each, sorted."""
    answer = "Siehe REV-0999 und REV-0998."
    assert warnings(answer, set()) == [
        "Warnhinweis: REV-0998 wurde nie abgerufen",
        "Warnhinweis: REV-0999 wurde nie abgerufen",
    ]


def test_answer_without_id_after_fetched_reviews_is_warned():
    """Fetched reviews and no ID in the answer hint at an injection, e.g. 'BLAU' (D-51)."""
    assert warnings("BLAU", set(sample_ids("PHM-101"))) == [
        "Warnhinweis: Antwort nennt keine review_id"
    ]


def test_correctly_cited_ids_give_no_warning():
    """Only fetched IDs in the answer: no warning."""
    first, second, *_ = sample_ids("PHM-101")
    answer = f"Positiv: wirkt ({first}). Negativ: Schwindel ({second})."
    assert warnings(answer, set(sample_ids("PHM-101"))) == []


def test_answer_without_id_and_without_fetched_reviews_gives_no_warning():
    """With statistics only there is no ID to cite, so a missing ID is no warning."""
    assert warnings("Kurzfazit: 70 Reviews, Durchschnitt 5,6.", set()) == []


def test_unknown_drug_has_no_data():
    """PHM-999 from both tools gives one line 'keine Daten' (D-57)."""
    results = [get_rating_statistics("PHM-999"), get_reviews("PHM-999")]
    assert data_basis(results) == ["PHM-999: keine Daten"]


def test_drug_with_data_elsewhere_is_not_reported_as_unknown():
    """'keine Daten' only stands if no other result brought data for that drug."""
    results = [unknown_drug("PHM-101"), get_rating_statistics("PHM-101")]
    assert data_basis(results) == ["PHM-101: Statistik über 70 Reviews"]


def test_statistics_and_sample_share_one_line():
    """Statistics and sample of one drug form one line with all sample IDs (D-27, D-39)."""
    results = [get_rating_statistics("PHM-101"), get_reviews("PHM-101")]
    assert data_basis(results) == [f"PHM-101: Statistik über 70 Reviews, {sample_part('PHM-101')}"]
    assert len(sample_ids("PHM-101")) == 12


def test_comparison_of_two_drugs_gives_two_lines_in_call_order():
    """A comparison gives one line per drug, in the order the drugs first appear (D-57)."""
    results = [
        get_rating_statistics("PHM-303"),
        get_rating_statistics("PHM-101"),
        get_reviews("PHM-101"),
        get_reviews("PHM-303"),
    ]
    assert data_basis(results) == [
        f"PHM-303: Statistik über 70 Reviews, {sample_part('PHM-303')}",
        f"PHM-101: Statistik über 70 Reviews, {sample_part('PHM-101')}",
    ]


def test_statistics_for_all_drugs_give_one_line_each():
    """get_rating_statistics without drug covers all six drugs (D-29)."""
    assert data_basis([get_rating_statistics()]) == [
        f"PHM-{number}: Statistik über 70 Reviews"
        for number in ["101", "202", "303", "404", "505", "606"]
    ]


def test_statistics_only_has_no_sample_part():
    """Without get_reviews the sample part is left out."""
    assert data_basis([get_rating_statistics("PHM-606")]) == ["PHM-606: Statistik über 70 Reviews"]


def test_sample_only_has_no_statistics_part():
    """Without get_rating_statistics the statistics part is left out (D-57)."""
    assert data_basis([get_reviews("PHM-606")]) == [f"PHM-606: {sample_part('PHM-606')}"]


def test_repeated_calls_for_a_drug_are_merged():
    """Two samples of one drug count their distinct IDs once; statistics stay on the line."""
    full = get_reviews("PHM-101")
    first = {**full, "reviews": full["reviews"][:8]}
    second = {**full, "reviews": full["reviews"][4:]}
    results = [first, get_rating_statistics("PHM-101"), second, get_rating_statistics("PHM-101")]
    assert data_basis(results) == [f"PHM-101: Statistik über 70 Reviews, {sample_part('PHM-101')}"]


def test_error_results_are_ignored():
    """Tool errors carry no data and add no line (D-50)."""
    results = [get_reviews(), {"error": "Die Argumente sind kein gültiges JSON."}]
    assert data_basis(results) == []
    assert finish_answer("Antwort", results) == "Antwort\n\nDatenbasis: keine Daten abgerufen"


def test_bold_markers_are_removed_and_single_stars_kept():
    """Only ** goes, other characters stay (D-51)."""
    text = "**Kurzfazit:** wirkt *meist* gut, Rating 7*"
    assert strip_bold(text) == "Kurzfazit: wirkt *meist* gut, Rating 7*"


def test_no_tool_calls_give_no_data_line():
    """Without any tool result the code says that no data was fetched."""
    assert finish_answer("Kurzfazit: Keine Daten abgerufen.", []) == (
        "Kurzfazit: Keine Daten abgerufen.\n\nDatenbasis: keine Daten abgerufen"
    )


def test_finish_answer_appends_data_basis_and_warnings():
    """The answer without bold, then the data basis, then the warnings, each block apart."""
    [cited, *_] = sample_ids("PHM-101")
    answer = f"**Kurzfazit:** wirkt ({cited}), aber Übelkeit (REV-0999)."
    results = [get_rating_statistics("PHM-101"), get_reviews("PHM-101")]
    assert finish_answer(answer, results) == (
        f"Kurzfazit: wirkt ({cited}), aber Übelkeit (REV-0999).\n\n"
        "Datenbasis:\n"
        f"PHM-101: Statistik über 70 Reviews, {sample_part('PHM-101')}\n\n"
        "Warnhinweis: REV-0999 wurde nie abgerufen"
    )


def test_bold_around_an_id_raises_no_warning():
    """A fetched ID in bold, **REV-…**, gives no warning."""
    [cited, *_] = sample_ids("PHM-101")
    finished = finish_answer(f"Positiv: wirkt (**{cited}**).", [get_reviews("PHM-101")])
    assert "Warnhinweis" not in finished


def test_agent_result_feeds_finish_answer():
    """End to end with the fake client (D-36): tool results of the loop become the data basis."""
    review_id = unfetched_id("PHM-202")
    client = FakeClient(
        [
            tool_response(
                ("get_rating_statistics", '{"drug": "PHM-202"}'),
                ("get_reviews", '{"drug": "phm 202"}'),
            ),
            tool_response(("get_reviews", '{"drug": "PHM-999"}')),
            text_response(f"**Kurzfazit:** gemischt ({review_id})."),
        ]
    )
    answer, results = run_agent(client, MODEL, "Wie bewerten Patienten PHM-202 und PHM-999?")
    assert finish_answer(answer, results) == (
        f"Kurzfazit: gemischt ({review_id}).\n\n"
        "Datenbasis:\n"
        f"PHM-202: Statistik über 70 Reviews, {sample_part('PHM-202')}\n"
        "PHM-999: keine Daten\n\n"
        f"Warnhinweis: {review_id} wurde nie abgerufen"
    )
