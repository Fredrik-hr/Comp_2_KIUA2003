"""Meeting brief: one PDF with every approved item, for the organiser to share.

Built only from reviewed briefs (removed extracts dropped, order applied) and the agenda.
Extracts are verbatim; the orientation section shows their beginning, cut at a sentence
boundary, and the appendix shows them in full. Rejected items are listed as "no brief";
skipped items with their reason; closed items with the case number only — never the title.

Rendered with PyMuPDF's Story (HTML -> PDF, no extra dependency). The layout runs twice:
the first pass records the page each item starts on, the second writes those numbers into
the list on the front page.
"""

from __future__ import annotations

import html
import io
from dataclasses import dataclass

import fitz

from . import assemble

A4 = fitz.paper_rect("a4")
MARGIN = 56

S = {
    "nb": {"title": "Brief til møtet", "items": "Saker", "page": "side", "printed": "trykt",
           "of": "av", "no_brief": "ingen brief", "closed": "lukket sak",
           "procedural": "formalitet – ikke behandlet", "scope": "utenfor omfang – ikke behandlet",
           "appendix": "Vedlegg: alle utdrag", "meeting_note": "Merknad fra møtesekretariatet",
           "source": "Kilde", "nothing": "Ingen utdrag.", "made": "Laget"},
    "nn": {"title": "Brief til møtet", "items": "Saker", "page": "side", "printed": "trykt",
           "of": "av", "no_brief": "ingen brief", "closed": "lukka sak",
           "procedural": "formalitet – ikkje handsama", "scope": "utanfor omfang – ikkje handsama",
           "appendix": "Vedlegg: alle utdrag", "meeting_note": "Merknad frå møtesekretariatet",
           "source": "Kjelde", "nothing": "Ingen utdrag.", "made": "Laga"},
    "en": {"title": "Meeting brief", "items": "Items", "page": "page", "printed": "printed",
           "of": "of", "no_brief": "no brief", "closed": "closed item",
           "procedural": "procedural – not processed", "scope": "out of scope – not processed",
           "appendix": "Appendix: all extracts", "meeting_note": "Note from the secretariat",
           "source": "Source", "nothing": "No extracts.", "made": "Made"},
}

CSS = """
* {font-family: sans-serif;}
body {font-size: 10pt; line-height: 1.35;}
h1 {font-size: 20pt; margin: 0 0 4pt 0;}
h2 {font-size: 14pt; margin: 16pt 0 2pt 0;}
h3 {font-size: 9pt; margin: 10pt 0 3pt 0; color: #555555;}
p {margin: 0 0 5pt 0;}
.meta {color: #555555; font-size: 9pt;}
.disc {border-left: 2pt solid #2d5b8a; padding-left: 6pt; color: #333333;}
.q {font-family: serif; font-size: 10pt; background-color: #f1efe8; padding: 4pt 6pt;
    margin: 0 0 2pt 0;}
.src {font-size: 8pt; color: #666666; margin: 0 0 6pt 0;}
.note {font-style: italic; font-size: 8.5pt; color: #444444;}
.org {border: 0.5pt solid #999999; padding: 4pt 6pt;}
table {border-collapse: collapse; width: 100%;}
td {padding: 2pt 4pt 2pt 0; vertical-align: top; font-size: 9.5pt;}
td.n {width: 15%;} td.p {width: 12%; text-align: right; color: #555555;}
"""


@dataclass
class ItemEntry:
    case_no: str
    title: str
    kind: str                 # approved | rejected | closed | procedural | scope
    brief: dict | None = None  # the reviewed brief for approved items
    note: str = ""


def _e(s: str | None) -> str:
    return html.escape(s or "")


def _ref(e: dict, lang: str, public_url: str | None) -> str:
    s = S[lang]
    printed = f" ({s['printed']} {_e(e['printed_page_label'])})" if e.get("printed_page_label") \
        else ""
    where = f"{_e(e['document_title'])}, {s['page']} {e['physical_page']}{printed}"
    if public_url:
        where += f" · {_e(public_url)}"
    why = assemble.why(e, lang)
    return where + (f" · {_e(why)}" if why else "")


def _html(meeting: dict, entries: list[ItemEntry], lang: str, note: str,
          public_url: str | None, pages: dict[str, int] | None) -> list[str]:
    """Three parts, each starting on a new page: front page, items, appendix."""
    s = S[lang]
    out = [f"<h1>{s['title']}</h1>",
           f"<p class='meta'>{_e(meeting['body'])} · {_e(meeting['date'])} · "
           f"{_e(meeting['municipality'])}</p>"]
    if public_url:
        out.append(f"<p class='meta'>{s['source']}: {_e(public_url)}</p>")
    out.append(f"<p class='disc'>{_e(assemble.DISCLAIMER[lang])}</p>")
    if note:
        out.append(f"<p class='org'><b>{s['meeting_note']}:</b> {_e(note)}</p>")
    out.append(f"<h2>{s['items']}</h2><table>")
    for i, it in enumerate(entries):
        if it.kind == "approved":
            num = str(pages.get(f"item{i}", "")) if pages else "000"
            out.append(f"<tr><td class='n'>{_e(it.case_no)}</td><td>{_e(it.title)}</td>"
                       f"<td class='p'>{s['page']} {num}</td></tr>")
        elif it.kind == "closed":   # never the title of a closed item
            out.append(f"<tr><td class='n'>{_e(it.case_no)}</td><td>{s['closed']}</td>"
                       "<td class='p'></td></tr>")
        else:
            label = s["no_brief"] if it.kind == "rejected" else s[it.kind]
            out.append(f"<tr><td class='n'>{_e(it.case_no)}</td><td>{_e(it.title)} – "
                       f"<i>{label}</i></td><td class='p'></td></tr>")
    out.append("</table>")
    front, out = "".join(out), []

    # Orientation per approved item.
    for i, it in enumerate(entries):
        if it.kind != "approved":
            continue
        b = it.brief
        out.append(f"<h2 id='item{i}'>{_e(it.case_no)} {_e(it.title)}</h2>")
        if it.note:
            out.append(f"<p class='org'><b>{s['meeting_note']}:</b> {_e(it.note)}</p>")
        groups = assemble.orientation(b["extracts"])
        if not groups:
            out.append(f"<p class='meta'>{s['nothing']}</p>")
        for g in groups:
            out.append(f"<h3>{_e(assemble.CATEGORY[lang][g['category']]).upper()}</h3>")
            for e in g["extracts"]:
                short, cut = assemble.shorten(e["text"])
                out.append(f"<p class='q'>{_e(short)}{' …' if cut else ''}</p>")
                out.append(f"<p class='src'>{_ref(e, lang, public_url)}</p>")

    items, out = "".join(out), []

    # Appendix: every kept extract in full.
    if any(it.kind == "approved" and it.brief["extracts"] for it in entries):
        out.append(f"<h2 id='appendix'>{s['appendix']}</h2>")
        for it in entries:
            if it.kind != "approved" or not it.brief["extracts"]:
                continue
            out.append(f"<h3>{_e(it.case_no)} {_e(it.title).upper()}</h3>")
            for e in it.brief["extracts"]:
                out.append(f"<p class='q'>{_e(e['text'])}</p>")
                out.append(f"<p class='src'>{_ref(e, lang, public_url)}</p>")
                if e.get("note"):
                    out.append(f"<p class='note'>{_e(assemble.NOTE_LABEL[lang])}: "
                               f"{_e(e['note'])}</p>")
    return [front, items, "".join(out)]


def _layout(parts: list[str]) -> tuple[bytes, dict[str, int]]:
    buf = io.BytesIO()
    writer = fitz.DocumentWriter(buf)
    where = A4 + (MARGIN, MARGIN, -MARGIN, -MARGIN - 14)
    positions: dict[str, int] = {}
    page = 0

    def record(pos) -> None:
        if pos.id and pos.id not in positions and pos.open_close & 1:
            positions[pos.id] = pos.page_num

    for body in (b for b in parts if b):
        story = fitz.Story(html=body, user_css=CSS)
        more = 1
        while more:
            page += 1
            dev = writer.begin_page(A4)
            more, _ = story.place(where)
            story.element_positions(record, {"page_num": page})
            story.draw(dev)
            writer.end_page()
    writer.close()
    return buf.getvalue(), positions


def _footer(pdf: bytes, lang: str, label: str) -> bytes:
    s = S[lang]
    doc = fitz.open(stream=pdf, filetype="pdf")
    n = doc.page_count
    for i, page in enumerate(doc, start=1):
        text = f"{label} · {s['page']} {i} {s['of']} {n}"
        page.insert_text((MARGIN, A4.height - MARGIN + 18), text, fontsize=8,
                         color=(0.4, 0.4, 0.4))
    return doc.tobytes(garbage=3, deflate=True)


def build(meeting: dict, entries: list[ItemEntry], lang: str, note: str = "",
          public_url: str | None = None) -> bytes:
    """The meeting brief as PDF bytes. `meeting` has body, date (dd.mm.yyyy), municipality."""
    _, pages = _layout(_html(meeting, entries, lang, note, public_url, None))
    pdf, _ = _layout(_html(meeting, entries, lang, note, public_url, pages))
    return _footer(pdf, lang, f"{meeting['body']} {meeting['date']}")
