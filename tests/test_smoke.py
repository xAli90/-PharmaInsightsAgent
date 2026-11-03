from pathlib import Path

CSV_PATH = Path(__file__).parent.parent / "data" / "pharma_reviews.csv"


def test_csv_exists():
    """The review data ships with the repository."""
    assert CSV_PATH.is_file()


def test_live_marker_is_registered(request):
    """The live marker is registered so live tests can be deselected."""
    markers = request.config.getini("markers")
    assert any(marker.startswith("live:") for marker in markers)
