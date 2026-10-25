"""S2 — Parse.

Per page: text, physical index and printed label. Segments are PyMuPDF text blocks
(paragraphs, list items, captions) or table rows, with IDs `doc:page:segment`. A heading
tree is built from font size and weight, with numbering patterns parsed from the text.
Invisible text (white or tiny) is stripped before segmentation (§10.1 repair).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

import fitz

from .. import paths
from ..models import Heading, PageInfo, ParsedDoc, Segment
from ..text import normalize

log = logging.getLogger(__name__)

PARSER_VERSION = "5"
HEADING_BOLD_SHARE = 0.75
MARGIN_BAND = 0.15    # header/footer candidates lie in the top or bottom 15% of a page
REPEAT_MIN_PAGES = 5  # a margin block repeated on this many pages is a running header
MIN_VISIBLE_SIZE = 3.0
_NUMBER = re.compile(r"^(?:(?:Chapter|Kapittel|Kapitel)\s+)?(\d+(?:\.\d+)*)\.?\s+(\S.*)$", re.I)
_PAGE_NO = re.compile(r"^(\d{1,4}|[ivxlcdm]{1,7})$", re.I)
_BARE_NUMBER = re.compile(r"^(?:(?:Chapter|Kapittel|Kapitel|Del|Part)\s+)?\d+(?:\.\d+)*\.?$", re.I)


class ParseError(RuntimeError):
    pass


def _is_bold(span: dict) -> bool:
    font = span["font"]
    return bool(span["flags"] & 16) or "Bold" in font or "BX" in font.upper()


def _is_visible(span: dict) -> bool:
    if span["size"] < MIN_VISIBLE_SIZE:
        return False
    c = span["color"]
    r, g, b = (c >> 16) & 255, (c >> 8) & 255, c & 255
    return not (r > 240 and g > 240 and b > 240)


def _block_lines(block: dict) -> tuple[list[str], list[dict], int]:
    """Visible line texts, visible spans, and number of hidden characters dropped."""
    lines, spans, hidden = [], [], 0
    for line in block.get("lines", []):
        parts = []
        for s in line["spans"]:
            if _is_visible(s):
                parts.append(s["text"])
                spans.append(s)
            else:
                hidden += len(s["text"].strip())
        if parts:
            lines.append("".join(parts))
    return lines, spans, hidden


def _in_margin(block: dict, height: float) -> bool:
    return block["bbox"][3] <= height * MARGIN_BAND or block["bbox"][1] >= height * (
        1 - MARGIN_BAND)


def _page_number_line(block: dict) -> str | None:
    for line in _block_lines(block)[0]:
        if _PAGE_NO.match(line.strip()):
            return line.strip()
    return None


def _margin_key(block: dict) -> str:
    return re.sub(r"\d+", "#", normalize("\n".join(_block_lines(block)[0])))


def detect_label(doc: fitz.Document, page: fitz.Page) -> tuple[str | None, str]:
    """Printed page label: the PDF's page label if defined, else a page number in the first
    or last text block when it lies in the margin band. Shared by S2 and V3."""
    if doc.get_page_labels():
        label = page.get_label()
        if label:
            return label, "pdf_label"
    h = page.rect.height
    blocks = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0]
    for b in blocks[:1] + blocks[-1:]:
        if _in_margin(b, h) and (n := _page_number_line(b)):
            return n, "detected"
    return None, "none"


def _running_headers(doc: fitz.Document) -> set[str]:
    keys: Counter[str] = Counter()
    for page in doc:
        h = page.rect.height
        for b in page.get_text("dict")["blocks"]:
            if b["type"] == 0 and _in_margin(b, h):
                keys[_margin_key(b)] += 1
    return {k for k, n in keys.items() if n >= REPEAT_MIN_PAGES and k}


def page_text(page: fitz.Page) -> str:
    """Normalised full text of a page — the reference text for V1."""
    return normalize(page.get_text())


def _body_size(doc: fitz.Document) -> float:
    sizes: Counter[float] = Counter()
    for page in doc:
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for s in line["spans"]:
                    sizes[round(s["size"], 1)] += len(s["text"])
    return sizes.most_common(1)[0][0] if sizes else 10.0


_WORD = re.compile(r"[A-Za-zÆØÅæøå]{3,}")


def _tables(page: fitz.Page, ptext: str) -> list[tuple[fitz.Rect, str | None, list[str]]]:
    """(bbox, header text, row texts) for ruled tables on the page.

    A detected table is kept only if it looks like a real table — a header with words and
    every row present verbatim in the page text. Diagrams and drawn figures also produce
    "tables" in find_tables, and those must stay as ordinary blocks.
    """
    out = []
    try:
        found = page.find_tables(strategy="lines")
    except Exception as e:  # noqa: BLE001 — table detection is best effort
        log.debug("find_tables failed on page %s: %s", page.number + 1, e)
        return out
    for t in found.tables:
        rows = t.extract()
        if t.col_count < 2 or len(rows) < 3:
            continue
        cells = [[normalize(c or "") for c in row] for row in rows]
        header_cells = [c for c in cells[0] if c]
        if len([c for c in header_cells if _WORD.search(c)]) < 2:
            continue
        row_texts = [" ".join(c for c in row if c) for row in cells[1:]]
        if not all(r and r in ptext for r in row_texts):
            continue
        out.append((fitz.Rect(t.bbox), " | ".join(header_cells), row_texts))
    return out


def parse(pdf_path: Path, sha256: str, url: str, title: str) -> ParsedDoc:
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001 — any open failure is a corrupt document
        raise ParseError(f"cannot open PDF: {e}") from e
    if doc.needs_pass or doc.is_encrypted:
        raise ParseError("PDF is encrypted")
    if doc.page_count == 0:
        raise ParseError("PDF has no pages")

    doc_id = f"doc_{sha256[:8]}"
    body = _body_size(doc)
    running = _running_headers(doc)

    # Pass 1: collect raw blocks with heading candidacy.
    raw: list[dict] = []
    pages: list[PageInfo] = []
    for page in doc:
        pno = page.number + 1
        label, source = detect_label(doc, page)
        h = page.rect.height
        ptext = page_text(page)
        tables = _tables(page, ptext)
        hidden_total = 0
        page_blocks = []
        for b in page.get_text("dict")["blocks"]:
            if b["type"] != 0:
                continue
            if _in_margin(b, h) and (_margin_key(b) in running or _page_number_line(b)):
                continue  # running header / footer / page number
            lines, spans, hidden = _block_lines(b)
            hidden_total += hidden
            text = normalize("\n".join(lines))
            if len(text) < 3:
                continue
            if any(fitz.Rect(b["bbox"]).intersects(t[0]) for t in tables):
                continue  # replaced by table rows below
            visible = [s for s in spans if s["text"].strip()]
            max_size = max((s["size"] for s in visible), default=0)
            chars = sum(len(s["text"].strip()) for s in visible)
            bold = sum(len(s["text"].strip()) for s in visible if _is_bold(s))
            # Share of bold characters, not all spans: headings such as "0.3 Big-O notation"
            # set single symbols in a non-bold math font.
            heading = (
                chars > 0
                and bold / chars >= HEADING_BOLD_SHARE
                and max_size >= body + 1.0
                and len(text) <= 140
            )
            kind = "heading" if heading else (
                "caption" if re.match(r"^(Figure|Table|Figur|Tabell)\s+\d", text) else "body"
            )
            page_blocks.append({"page": pno, "text": text, "kind": kind,
                                "size": round(max_size * 2) / 2, "hidden": hidden})
        for _, header, rows in tables:
            for row in rows:
                page_blocks.append({"page": pno, "text": row, "kind": "table_row",
                                    "size": 0, "hidden": 0, "header": header})
        # Merge a bare heading number with the title after it ("Chapter 3" + "Decompositions
        # of graphs"), but never two titled headings ("1.1 Basic arithmetic", "1.1.1 Addition").
        merged: list[dict] = []
        for blk in page_blocks:
            if merged and blk["kind"] == "heading" and merged[-1]["kind"] == "heading" \
                    and _BARE_NUMBER.match(merged[-1]["text"]):
                merged[-1]["text"] = f"{merged[-1]['text']} {blk['text']}"
                merged[-1]["size"] = max(merged[-1]["size"], blk["size"])
            else:
                merged.append(blk)
        raw.extend(merged)
        has_text = len(ptext) >= 20
        if not has_text and page.get_images():
            log.warning("S2 page %s of %s has no text layer (scanned?)", pno, title)
        pages.append(PageInfo(page=pno, label=label, label_source=source,
                              has_text_layer=has_text, hidden_chars_removed=hidden_total))

    # Heading levels from distinct heading sizes, largest first.
    sizes = sorted({b["size"] for b in raw if b["kind"] == "heading"}, reverse=True)
    level_of = {s: i + 1 for i, s in enumerate(sizes)}

    # Pass 2: segment IDs, heading tree, section paths.
    segments: list[Segment] = []
    headings: list[Heading] = []
    stack: list[Heading] = []
    page_texts: dict[int, str] = {}
    search_from: dict[int, int] = {}
    per_page: Counter[int] = Counter()
    for seq, b in enumerate(raw):
        pno = b["page"]
        per_page[pno] += 1
        sid = f"{doc_id}:p{pno:04d}:s{per_page[pno]:03d}"
        if b["kind"] == "heading":
            if pno not in page_texts:
                page_texts[pno] = page_text(doc[pno - 1])
            off = page_texts[pno].find(b["text"], search_from.get(pno, 0))
            if off < 0:
                off = page_texts[pno].find(b["text"])
            search_from[pno] = max(off, 0) + 1
            m = _NUMBER.match(b["text"])
            hd = Heading(text=b["text"], number=m.group(1) if m else None,
                         level=level_of[b["size"]], page=pno, offset=max(off, 0), seq=seq)
            while stack and stack[-1].level >= hd.level:
                stack.pop()
            stack.append(hd)
            headings.append(hd)
        flags = ["hidden_text_removed"] if b["hidden"] else []
        segments.append(Segment(
            id=sid, doc_id=doc_id, page=pno, seq=seq, kind=b["kind"], text=b["text"],
            section_path=[h.text for h in stack], table_header=b.get("header"), flags=flags,
        ))

    parsed = ParsedDoc(doc_id=doc_id, sha256=sha256, url=url, title=title,
                       page_count=doc.page_count, pages=pages, headings=headings,
                       segments=segments)
    log.info("S2 %s: %d pages, %d segments, %d headings", title, doc.page_count,
             len(segments), len(headings))
    return parsed


def parse_cached(pdf_path: Path, sha256: str, url: str, title: str) -> ParsedDoc:
    out = paths.DERIVED / sha256 / f"parsed_v{PARSER_VERSION}.json"
    if out.exists():
        doc = ParsedDoc.model_validate_json(out.read_text(encoding="utf-8"))
        return doc.model_copy(update={"url": url, "title": title})
    doc = parse(pdf_path, sha256, url, title)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc.model_dump_json(), encoding="utf-8")
    return doc
