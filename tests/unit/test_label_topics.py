import pytest
import typer

from eval import label, metrics

SCHEME = """Hovedtema: Kjernekraft – naturvirkninger

Underemner (velg de som passer for hvert avsnitt)

Arealbruk: hvor mye areal et kraftverk legger beslag på
Følgeinngrep: kraftledninger, veier og annen infrastruktur
"""


def test_scheme_separates_theme_from_subtopics():
    theme, topics = label.parse_scheme(SCHEME)
    assert theme == "Kjernekraft – naturvirkninger"
    assert list(topics) == ["Arealbruk", "Følgeinngrep"]


def test_unknown_topic_refused_and_case_ignored():
    _, topics = label.parse_scheme(SCHEME)
    assert label.resolve_topics(["arealbruk"], topics) == ["Arealbruk"]
    with pytest.raises(typer.BadParameter):
        label.resolve_topics(["Strålevern"], topics)


def test_recall_by_topic(monkeypatch):
    page = "Et kraftverk bruker lite areal. Nye kraftledninger trengs. Annet."
    monkeypatch.setattr(metrics, "_page", lambda url, p: page)
    gold = {"passages": [
        {"document": "d", "physical_page": 1, "quote": "Et kraftverk bruker lite areal.",
         "topics": ["Arealbruk"]},
        {"document": "d", "physical_page": 1, "quote": "Nye kraftledninger trengs.",
         "topics": ["Følgeinngrep", "Arealbruk"]}]}
    brief = {"case_no": "PS 1/26", "status": "awaiting_review", "extracts": [
        {"source_url": "d#page=1", "physical_page": 1, "segment_id": "s1",
         "text": "Et kraftverk bruker lite areal.", "found_via": "search"}]}
    row = metrics.score_item(brief, gold)
    assert row["found_by_topic"] == {"Arealbruk": [1, 2], "Følgeinngrep": [0, 1]}
    assert row["missed"][0]["topics"] == ["Følgeinngrep", "Arealbruk"]
    assert metrics.aggregate([row])["found_by_topic"] == row["found_by_topic"]
