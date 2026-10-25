import pytest

from briefer import assemble, verify
from briefer.parse import parse


@pytest.fixture
def setup(simple_pdf, monkeypatch):
    d = parse(simple_pdf, "ab" * 32, "local:doc.pdf", "Doc")
    monkeypatch.setattr(verify, "_url_ok", lambda url: url == "local:doc.pdf")
    src = verify.SourceDocs({d.doc_id: (d, simple_pdf)})
    seg = next(s for s in d.segments if "1 234,5" in s.text)
    return d, src, seg


def ex(d, seg, **over):
    e = assemble.extract_for(seg, d, "direct", "search", "Driftsrammen for opplæring.")
    return e.model_copy(update=over)


def test_true_extract_passes_all(setup):
    d, src, seg = setup
    assert verify.check_extract(ex(d, seg), src) == []


def test_v1_altered_text_fails(setup):
    d, src, seg = setup
    fails = verify.check_extract(ex(d, seg, text=seg.text.replace("1 234,5", "1 334,5")), src)
    assert any(f.startswith("V1") for f in fails)


def test_v2_note_may_not_add_numbers(setup):
    d, src, seg = setup
    fails = verify.check_extract(ex(d, seg, note="Økes med 99 mill. kr"), src)
    assert any("V2 note" in f for f in fails)


def test_v2_norwegian_number_formats():
    assert verify.numbers("1 234,5 mill. kr og 12,3 % i 2027–2030") == {
        "1234,5", "12,3", "2027", "2030"}


def test_note_only_v2_failure_drops_note_keeps_extract(setup):
    d, src, seg = setup
    brief = {"case_no": "PS 1/26", "status": "draft", "brief_language": "nb", "extracts": [],
             "verification": {"all_passed": True, "checks": []}, "run_id": "r",
             "disclaimer": "x"}
    out, checked, failed = verify.verify(brief, [ex(d, seg, note="Se sak PS 4/26")], src, 1)
    assert failed == 0 and out["extracts"][0]["note"] == ""
    assert out["verification"]["notes_dropped"][0]["failures"][0].startswith("V2 note")


def test_v3_wrong_label_fails(setup):
    d, src, seg = setup
    assert any(f.startswith("V3") for f in
               verify.check_extract(ex(d, seg, printed_page_label="7"), src))


def test_v4_wrong_section_fails(setup):
    d, src, seg = setup
    fails = verify.check_extract(ex(d, seg, section_path=["4.2 Opplæring"]), src)
    assert any(f.startswith("V4") for f in fails)


def test_v5_fragment_must_match_page(setup):
    d, src, seg = setup
    fails = verify.check_extract(ex(d, seg, source_url="local:doc.pdf#page=2"), src)
    assert any(f.startswith("V5") for f in fails)
    fails = verify.check_extract(ex(d, seg, source_url="local:missing.pdf#page=1"), src)
    assert any("does not resolve" in f for f in fails)


def test_v6_v7_on_brief(setup):
    d, src, seg = setup
    brief = {"case_no": "PS 1/26", "status": "skipped", "brief_language": "nb", "extracts": [],
             "verification": {"all_passed": True, "checks": []}, "run_id": "r",
             "disclaimer": assemble.DISCLAIMER["nb"]}
    out, _, _ = verify.verify(dict(brief), [], src, llm_calls=0)
    assert out["verification"]["all_passed"]
    out, _, _ = verify.verify(dict(brief), [], src, llm_calls=2)
    assert not out["verification"]["all_passed"]
    assert any(c.startswith("V7") for c in out["verification"]["checks"])
    bad = {**brief, "status": "bogus"}
    out, _, _ = verify.verify(bad, [], src, llm_calls=0)
    assert any(c.startswith("V6") for c in out["verification"]["checks"])


def test_failing_extract_removed_from_brief(setup):
    d, src, seg = setup
    brief = {"case_no": "PS 1/26", "status": "draft", "brief_language": "nb", "extracts": [],
             "verification": {"all_passed": True, "checks": []}, "run_id": "r",
             "disclaimer": "x"}
    good, bad = ex(d, seg), ex(d, seg, text="Dette står ikke i dokumentet.")
    out, checked, failed = verify.verify(brief, [good, bad], src, llm_calls=1)
    assert (checked, failed) == (2, 1)
    assert [e["text"] for e in out["extracts"]] == [seg.text]
    assert out["verification"]["removed"][0]["failures"][0].startswith("V1")
