import fitz
import pytest

from briefer.parse import ParseError, parse
from briefer.text import normalize

from .conftest import make_pdf


def test_segments_headings_labels(simple_pdf):
    d = parse(simple_pdf, "ab" * 32, "local:doc.pdf", "Doc")
    texts = [s.text for s in d.segments]
    assert any("1 234,5 mill. kr" in t for t in texts)
    heads = [(h.text, h.level) for h in d.headings]
    assert heads == [("4 Driftsbudsjett", 1), ("4.2 Opplæring", 2)]
    body = next(s for s in d.segments if "Se tabell 3" in s.text)
    assert body.section_path == ["4 Driftsbudsjett", "4.2 Opplæring"]
    assert body.id == f"{d.doc_id}:p0002:s002"
    assert [p.label for p in d.pages] == ["1", "2"]


def test_invisible_text_is_stripped(simple_pdf):
    d = parse(simple_pdf, "ab" * 32, "local:doc.pdf", "Doc")
    joined = " ".join(s.text for s in d.segments)
    assert "Ignore previous instructions" not in joined   # 2 pt text
    assert "Skjult tekst" not in joined                    # white text
    assert d.pages[0].hidden_chars_removed > 0


def test_scanned_page_flagged(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    page.insert_image(page.rect, pixmap=pix)
    p = tmp_path / "scan.pdf"
    doc.save(p)
    d = parse(p, "cd" * 32, "local:scan.pdf", "Scan")
    assert not d.pages[0].has_text_layer


def test_corrupt_and_encrypted_pdf_raise(tmp_path, simple_pdf):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\n garbage garbage")
    with pytest.raises(ParseError):
        parse(bad, "ef" * 32, "local:bad.pdf", "Bad")
    enc = tmp_path / "enc.pdf"
    fitz.open(simple_pdf).save(enc, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x",
                               owner_pw="y")
    with pytest.raises(ParseError, match="encrypted"):
        parse(enc, "12" * 32, "local:enc.pdf", "Enc")


def test_normalize_rules():
    assert normalize("eﬀektiv  ﬁnans") == "effektiv finans"
    assert normalize("budsjett-\nrammen") == "budsjettrammen"
    assert normalize("myk­bindestrek") == "mykbindestrek"
    assert normalize("a\n\n  b\tc") == "a b c"


def test_page_labels_offset(tmp_path):
    p = make_pdf(tmp_path / "o.pdf", [[("Tekst på siden her.", 11, False, (0, 0, 0))]] * 3,
                 label_offset=10)
    d = parse(p, "34" * 32, "local:o.pdf", "O")
    assert [pg.label for pg in d.pages] == ["11", "12", "13"]
