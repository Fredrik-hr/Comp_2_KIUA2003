"""Why an extract is in a brief: S7 query tracking, S7b innstilling, S8 category, S9 output."""

import hashlib
from pathlib import Path

import jsonschema
import pytest

from briefer import agent, assemble, innstilling, paths, privacy, retrieve, verify
from briefer.agenda import Item
from briefer.index import Index
from briefer.models import PageInfo, ParsedDoc, Segment

ROOT = Path(__file__).resolve().parents[2]
REAL_PDF = ROOT / "fylkesutvalget_2026-09-29.pdf"


def _seg(page, seq, text, kind="body", section=("Sak",), flags=()):
    return Segment(id=f"doc_abababab:p{page:04d}:s{seq:03d}", doc_id="doc_abababab", page=page,
                   seq=page * 100 + seq, kind=kind, text=text, section_path=list(section),
                   flags=list(flags))


def _doc(segments):
    pages = sorted({s.page for s in segments})
    return ParsedDoc(doc_id="doc_abababab", sha256="0" * 64, url="local:doc.pdf", title="Doc",
                     page_count=max(pages),
                     pages=[PageInfo(page=p, label=str(p), label_source="pdf_label",
                                     has_text_layer=True) for p in pages],
                     headings=[], segments=segments)


CASE_PAPER = [
    _seg(3, 1, "Arkivreferanse: 2026/1-1"),
    _seg(3, 2, "Utvalg Møtedato Saksnummer"),
    _seg(3, 3, "Fylkesutvalget 29.09.2026 93/26"),
    _seg(3, 4, "Svar til høring Fylkeskommunedirektørens innstilling til vedtak:", "heading"),
    _seg(3, 5, "1. Fylkesutvalget støtter forslaget om et kompetanseprogram."),
    _seg(3, 6, "2. Høringsfrist er satt til: 11.11.2026"),
    _seg(3, 7, "Kari Nordmann Fylkeskommunedirektør", flags=("pii:name",)),
    _seg(3, 8, "Vedlegg"),
    _seg(4, 1, "Bakgrunn: Saken ble sendt på høring i april."),
    # later reference to the same case number must not start a second block
    _seg(9, 1, "Protokoll fra møtet 93/26"),
]


# --- S7b innstilling ---------------------------------------------------------------------

def test_innstilling_heading_then_points():
    segs = innstilling.find("PS 93/26", _doc(CASE_PAPER))
    assert [s.text[:2] for s in segs] == ["1.", "2."]   # stops at the signature (pii)


def test_innstilling_in_same_segment_as_label():
    doc = _doc([_seg(5, 1, "Fylkesutvalget 13.10.2026 100/26"),
                _seg(5, 2, "Oppfølging Fylkeskommunedirektørens innstilling til vedtak: "
                           "Fylkesutvalget gir direktøren fullmakt."),
                _seg(5, 3, "Saksopplysninger: ...")])
    segs = innstilling.find("PS 100/26", doc)
    assert [s.seq for s in segs] == [502]


def test_innstilling_not_found_is_empty():
    assert innstilling.find("PS 7/26", _doc(CASE_PAPER)) == []
    assert innstilling.find("Godkjenning", _doc(CASE_PAPER)) == []
    no_label = _doc([_seg(3, 1, "Fylkesutvalget 29.09.2026 93/26"), _seg(3, 2, "Tekst.")])
    assert innstilling.find("PS 93/26", no_label) == []


@pytest.mark.skipif(not REAL_PDF.exists(), reason="fylkesutvalget_2026-09-29.pdf not present")
def test_innstilling_real_meeting():
    sha = hashlib.sha256(REAL_PDF.read_bytes()).hexdigest()
    cached = next((paths.ROOT / "data" / "derived" / sha).glob("parsed_v*.json"), None) \
        if (paths.ROOT / "data" / "derived" / sha).exists() else None
    if cached is None:
        pytest.skip("parsed cache for the real meeting not present (run the pipeline once)")
    doc, _ = privacy.screen(ParsedDoc.model_validate_json(cached.read_text(encoding="utf-8")))
    for case_no in ("PS 93/26", "PS 94/26", "PS 95/26", "PS 96/26", "PS 97/26", "PS 98/26"):
        segs = innstilling.find(case_no, doc)
        assert segs, case_no
        assert not any(f.startswith("pii:") for s in segs for f in s.flags)
    first = innstilling.find("PS 93/26", doc)
    assert first[0].text.startswith("1. Fylkesutvalget vurderer")


# --- S7 query tracking -------------------------------------------------------------------

def test_retrieve_records_query_for_hits_and_neighbours():
    segs = [_seg(1, 1, "Driftsrammen for skolene økes neste år.", section=("Budsjett",)),
            _seg(1, 2, "Rammen gjelder fra januar og omfatter alle skoler.", section=("Budsjett",)),
            _seg(2, 1, "Kollektivtrafikk og busser i distriktene.", section=("Samferdsel",))]
    idx = Index(segs)
    cands = {c.seg.id: c for c in retrieve.retrieve(idx, ["driftsrammen"], {"doc_abababab"}, {})}
    hit = cands["doc_abababab:p0001:s001"]
    assert (hit.via, hit.query) == ("search", "driftsrammen")
    near = cands["doc_abababab:p0001:s002"]
    assert near.via in ("section", "neighbour") and near.query == "driftsrammen"


# --- S8 category -------------------------------------------------------------------------

class StubLLM:
    def __init__(self, answers):
        self.answers = list(answers)
        self.schemas = []

    def complete_json(self, stage, messages, schema, **_):
        self.schemas.append(schema)
        out = self.answers.pop(0)
        jsonschema.validate(out, schema)  # what LLMClient does
        return out


def test_pointwise_returns_category_and_query():
    seg = _seg(1, 1, "Driftsrammen for skolene økes.")
    cand = retrieve.Candidate(seg, 1.0, "search", "driftsrammen")
    llm = StubLLM([{"relevance": "direct", "category": "consequences", "note": "Ramme."}])
    item = Item(case_no="PS 1/26", type="case", title="Budsjett", closed=False, in_scope=True)
    res = agent.run_pointwise(item, {"topic": "budsjett"}, [cand], llm, "nb")
    assert res.selections[0]["category"] == "consequences"
    assert res.queries[seg.id] == "driftsrammen"


def test_schema_requires_known_category():
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"relevance": "direct", "note": "x"}, agent.POINTWISE_SCHEMA)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"relevance": "direct", "category": "summary", "note": "x"},
                            agent.POINTWISE_SCHEMA)
    sel = {"segment_id": "doc_abababab:p0001:s001", "relevance": "direct", "note": "x"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"action": "finish", "nothing_found": False, "selections": [sel]},
                            agent.FINISH_SCHEMA)


# --- S9 output ---------------------------------------------------------------------------

def _brief(extracts):
    return {"case_no": "PS 1/26", "title": "Budsjett", "status": "awaiting_review",
            "brief_language": "nb", "extracts": extracts, "run_id": "r1",
            "verification": {"all_passed": True, "checks": []},
            "disclaimer": assemble.DISCLAIMER["nb"]}


def test_extract_why_fields_highlight_and_schema():
    doc = _doc([_seg(1, 1, "Driftsrammen for skolene økes, jf. driftsrammen i fjor.")])
    seg = doc.segments[0]
    e = assemble.extract_for(seg, doc, "direct", "search", "Om rammen.", "consequences",
                             "driftsrammen skolene")
    assert e.matched_terms == ["Driftsrammen", "skolene", "driftsrammen"]
    brief = _brief([e.model_dump()])
    assert verify.v6_schema(brief) is None
    html = assemble.to_html(brief)
    assert "<mark>Driftsrammen</mark> for <mark>skolene</mark>" in html
    assert "Hvorfor: Konsekvenser · treff på søket «driftsrammen skolene»" in html
    md = assemble.to_markdown(brief)
    assert "> Driftsrammen for skolene" in md        # Markdown text is never marked up
    assert "Hvorfor: Konsekvenser" in md


def test_innstilling_extract_why_and_schema():
    doc = _doc(CASE_PAPER)
    e = assemble.extract_for(doc.segments[4], doc, "direct", "innstilling", "", "decision")
    brief = _brief([e.model_dump()])
    assert verify.v6_schema(brief) is None
    assert assemble.why(e.model_dump(), "nb") == (
        "Hva skal vedtas · funnet av koden i innstillingen til vedtak")


def test_old_extract_without_why_fields_still_renders():
    old = {"segment_id": "doc_abababab:p0001:s001", "text": "Tekst.", "document_title": "Doc",
           "source_url": "local:doc.pdf#page=1", "physical_page": 1, "printed_page_label": "1",
           "section_path": [], "relevance": "direct", "found_via": "search", "note": "",
           "table_header": None}
    brief = _brief([old])
    assert verify.v6_schema(brief) is None
    assert "Hvorfor" not in assemble.to_html(brief)
