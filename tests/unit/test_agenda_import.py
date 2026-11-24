"""Agenda import: møteinnkalling (PDF / .docx) -> draft -> confirmed agenda."""

from pathlib import Path

import docx
import pytest
import yaml

from briefer import agenda_import as ai
from briefer.agenda import load

from .conftest import make_pdf

ROOT = Path(__file__).resolve().parents[2]
REAL_PDF = ROOT / "fylkesutvalget_2026-09-29.pdf"
REAL_AGENDA = ROOT / "tests" / "cases" / "fylkesutvalget_2026-09-29" / "agenda.yaml"
B = (0, 0, 0)


def _line(text):
    return (text, 11, False, B)


@pytest.fixture
def saksliste_pdf(tmp_path):
    return make_pdf(tmp_path / "innkalling.pdf", [
        [_line(x) for x in ["Utvalg:", "Hovedutvalg for samferdsel", "Dato:", "03.11.2026",
                            "Møteinnkalling", "Testvik kommune"]],
        [_line(x) for x in ["Saksliste", "Utvalgssaksnr.", "Tittel",
                            "PS 12/26", "Budsjett 2027 for samferdsel",
                            "PS 13/26", "Ny skolerute for Testvik - høring av",
                            "planprogram",
                            "RS 4/26", "Referat fra trafikksikkerhetsutvalget",
                            "PS 14/26", "Kjøp av eiendom", "X",
                            "OS 2/26", "Spørsmål fra Kari Nordmann om skolebuss",
                            "PS = Politisk sak"]],
        # case paper: the number repeats without the prefix, and must not add an item
        [_line(x) for x in ["Saksframlegg", "12/26", "Budsjett 2027 for samferdsel",
                            "Se sak PS 99/25 fra i fjor."]],
    ])


def _confirm(draft, closed=False, in_scope=True):
    for it in draft.items:
        it.closed, it.in_scope = closed, in_scope


def test_pdf_saksliste(saksliste_pdf):
    d = ai.convert(saksliste_pdf)
    assert (d.body, d.date, d.municipality) == (
        "Hovedutvalg for samferdsel", "2026-11-03", "Testvik kommune")
    assert d.meeting_id == "hovedutvalg_for_samferdsel_2026-11-03"
    assert [(i.case_no, i.type) for i in d.items] == [
        ("PS 12/26", "case"), ("PS 13/26", "case"), ("RS 4/26", "information"),
        ("PS 14/26", "case"), ("OS 2/26", "question")]
    assert d.items[1].title == "Ny skolerute for Testvik - høring av planprogram"
    assert d.items[3].suggested_closed and d.items[3].title == "Kjøp av eiendom"
    assert all(i.closed is None and i.in_scope is None for i in d.items)  # never defaulted


def test_name_in_title_is_flagged_and_blocks(saksliste_pdf):
    d = ai.convert(saksliste_pdf)
    flagged = [i.case_no for i in d.items if i.name_flags]
    assert flagged == ["OS 2/26"]
    _confirm(d)
    with pytest.raises(ai.AgendaImportError, match="OS 2/26"):
        ai.to_agenda(d, None)
    d.items[4].title = "Spørsmål fra en representant om skolebuss"
    ai.flag_names(d)
    ai.to_agenda(d, None)


def test_unconfirmed_draft_is_refused(saksliste_pdf):
    d = ai.convert(saksliste_pdf)
    d.items = d.items[:2]
    d.items[0].closed, d.items[0].in_scope = False, True
    with pytest.raises(ai.AgendaImportError) as e:
        ai.to_agenda(d, None)
    assert "PS 13/26: choose closed" in str(e.value)
    assert "PS 12/26" not in str(e.value)


def test_confirmed_draft_passes_s0(saksliste_pdf, tmp_path):
    d = ai.convert(saksliste_pdf)
    d.items = d.items[:4]
    _confirm(d)
    raw = ai.to_agenda(d, ai.attachment_for(d, saksliste_pdf))
    p = tmp_path / "agenda.yaml"
    p.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")
    agenda = load(p)
    assert len(agenda.items) == 4
    assert agenda.items[0].attachments[0].url.startswith("local:")
    assert "&id" not in p.read_text(encoding="utf-8")  # no YAML aliases


def test_cli_draft_is_rejected_by_s0(saksliste_pdf, tmp_path):
    d = ai.convert(saksliste_pdf)
    p = tmp_path / "x.draft.yaml"
    p.write_text(ai.draft_yaml(d, None), encoding="utf-8")
    text = p.read_text(encoding="utf-8")
    assert "# CONFIRM" in text and "PS 14/26: marked closed" in text
    with pytest.raises(Exception, match="closed"):
        load(p)


def test_docx_table(tmp_path):
    doc = docx.Document()
    doc.add_paragraph("Utvalg: Kontrollutvalget")
    doc.add_paragraph("Dato: 05.12.2026")
    doc.add_paragraph("Testvik kommune")
    t = doc.add_table(rows=0, cols=3)
    for row in [("PS 7/26", "Revisjonsplan 2027", ""), ("PS 8/26", "Sak om personalforhold",
                                                        "Offl. § 13"),
                ("RS 3/26", "Protokoll fra forrige møte", "")]:
        cells = t.add_row().cells
        for c, v in zip(cells, row, strict=True):
            c.text = v
    p = tmp_path / "innkalling.docx"
    doc.save(p)
    d = ai.convert(p)
    assert (d.body, d.date) == ("Kontrollutvalget", "2026-12-05")
    assert [(i.case_no, i.title, i.suggested_closed) for i in d.items] == [
        ("PS 7/26", "Revisjonsplan 2027", False),
        ("PS 8/26", "Sak om personalforhold", True),
        ("RS 3/26", "Protokoll fra forrige møte", False)]


def test_unsupported_and_empty(tmp_path):
    with pytest.raises(ai.AgendaImportError, match="unsupported"):
        ai.convert(tmp_path / "a.txt")
    empty = make_pdf(tmp_path / "e.pdf", [[_line("Ingen saker her")]])
    with pytest.raises(ai.AgendaImportError, match="no agenda items"):
        ai.convert(empty)


@pytest.mark.skipif(not REAL_PDF.exists(), reason="fylkesutvalget_2026-09-29.pdf not present")
def test_real_fylkesutvalget_matches_agenda():
    d = ai.convert(REAL_PDF)
    want = yaml.safe_load(REAL_AGENDA.read_text(encoding="utf-8"))
    assert d.meeting_id == want["meeting"]["id"]
    assert d.body == want["meeting"]["body"]
    assert d.municipality == want["meeting"]["municipality"]
    assert [(i.case_no, i.title) for i in d.items] == [
        (i["case_no"], i["title"]) for i in want["items"]]
    assert not any(i.name_flags for i in d.items)
