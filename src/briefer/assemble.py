"""S9 — Assemble.

Copies text by segment ID from the parsed source (never from the model), attaches page,
label, section and link, and renders JSON, Markdown and HTML.
"""

from __future__ import annotations

import html

from .models import Extract, ParsedDoc, Segment

DISCLAIMER = {
    "nb": "Utdrag som supplement til de fullstendige dokumentene, ikke en erstatning.",
    "nn": "Utdrag som supplement til dei fullstendige dokumenta, ikkje ei erstatning.",
    "en": "Supplement to the full documents, not a replacement.",
}
NOTE_LABEL = {"nb": "Maskinskrevet merknad", "nn": "Maskinskriven merknad",
              "en": "Machine-written note"}
STRINGS = {
    "nb": {"page": "side", "printed": "trykt side", "nothing": "Ingen relevante utdrag funnet.",
           "skipped": "Ikke behandlet", "attachments": "Vedlegg", "unsearchable":
           "Sider som ikke kunne søkes i", "direct": "Direkte relevant",
           "supporting": "Støttende", "cross_reference": "Kryssreferanse"},
    "nn": {"page": "side", "printed": "trykt side", "nothing": "Fann ingen relevante utdrag.",
           "skipped": "Ikkje handsama", "attachments": "Vedlegg", "unsearchable":
           "Sider som ikkje kunne søkjast i", "direct": "Direkte relevant",
           "supporting": "Støttande", "cross_reference": "Kryssreferanse"},
    "en": {"page": "page", "printed": "printed page", "nothing": "No relevant passages found.",
           "skipped": "Not processed", "attachments": "Attachments", "unsearchable":
           "Pages that could not be searched", "direct": "Directly relevant",
           "supporting": "Supporting", "cross_reference": "Cross-reference"},
}
ORDER = {"direct": 0, "supporting": 1, "cross_reference": 2}


def extract_for(seg: Segment, doc: ParsedDoc, relevance: str, found_via: str,
                note: str) -> Extract:
    label = next((p.label for p in doc.pages if p.page == seg.page), None)
    return Extract(
        segment_id=seg.id, text=seg.text, document_title=doc.title,
        source_url=f"{doc.url}#page={seg.page}", physical_page=seg.page,
        printed_page_label=label, section_path=seg.section_path, relevance=relevance,
        found_via=found_via, note=note.strip().splitlines()[0][:300] if note.strip() else "",
        table_header=seg.table_header,
    )


def order(extracts: list[Extract], seq: dict[str, int]) -> list[Extract]:
    return sorted(extracts, key=lambda e: (ORDER[e.relevance], e.document_title,
                                           seq.get(e.segment_id, 0)))


def to_markdown(brief: dict) -> str:
    lang = brief["brief_language"]
    s = STRINGS[lang]
    out = [f"# {brief['case_no']} {brief.get('title', '')}".rstrip(), "",
           f"> {brief['disclaimer']}", "",
           f"Status: **{brief['status']}** · run `{brief['run_id']}`", ""]
    if brief["status"] == "skipped":
        out += [f"{s['skipped']}: {brief.get('skip_reason', '')}", ""]
    elif not brief["extracts"]:
        out += [s["nothing"], ""]
    group = None
    for e in brief["extracts"]:
        if e["relevance"] != group:
            group = e["relevance"]
            out += [f"## {s[group]}", ""]
        label = f" ({s['printed']} {e['printed_page_label']})" if e["printed_page_label"] else ""
        out += ["> " + e["text"].replace("\n", "\n> "), ""]
        if e.get("table_header"):
            out += [f"_Table header: {e['table_header']}_", ""]
        out += [f"{e['document_title']} · {s['page']} {e['physical_page']}{label} · "
                f"{' › '.join(e['section_path'])} · [{e['source_url']}]({e['source_url']})", ""]
        if e["note"]:
            out += [f"*{NOTE_LABEL[lang]}: {e['note']}*", ""]
    if brief.get("attachments"):
        out += [f"## {s['attachments']}", ""]
        out += [f"- [{a['title']}]({a['url']})" for a in brief["attachments"]] + [""]
    if brief.get("unsearchable_pages"):
        out += [f"{s['unsearchable']}: {', '.join(brief['unsearchable_pages'])}", ""]
    return "\n".join(out)


_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a65;--rule:#dedbd2;--quote:#f1efe8;--accent:#2d5b8a}
@media (prefers-color-scheme: dark){:root{--bg:#1b1b1a;--fg:#ecebe6;--muted:#a3a19a;
--rule:#3a3936;--quote:#262624;--accent:#8db4dc}}
body{background:var(--bg);color:var(--fg);font:16px/1.55 Georgia,serif;max-width:46rem;
margin:2rem auto;padding:0 16px}
h1{font-size:1.5rem;margin-bottom:.25rem} h2{font-size:1.1rem;margin-top:2rem;
border-bottom:1px solid var(--rule);padding-bottom:.25rem}
.disclaimer{border-left:3px solid var(--accent);padding:.5rem .75rem;color:var(--muted)}
blockquote{background:var(--quote);margin:1rem 0 .25rem;padding:.75rem 1rem;
white-space:pre-wrap;font-family:system-ui,sans-serif;font-size:.95rem}
.ref{font:.85rem system-ui,sans-serif;color:var(--muted)} .ref a{color:var(--accent)}
.note{font-style:italic;font-size:.9rem} .meta{font:.85rem system-ui,sans-serif;color:var(--muted)}
"""


def to_html(brief: dict) -> str:
    lang = brief["brief_language"]
    s = STRINGS[lang]
    e_ = html.escape
    body = [f"<h1>{e_(brief['case_no'])} {e_(brief.get('title', ''))}</h1>",
            f"<p class=meta>Status: <b>{e_(brief['status'])}</b> · run {e_(brief['run_id'])}</p>",
            f"<p class=disclaimer>{e_(brief['disclaimer'])}</p>"]
    if brief["status"] == "skipped":
        body.append(f"<p>{s['skipped']}: {e_(brief.get('skip_reason') or '')}</p>")
    elif not brief["extracts"]:
        body.append(f"<p>{s['nothing']}</p>")
    group = None
    for e in brief["extracts"]:
        if e["relevance"] != group:
            group = e["relevance"]
            body.append(f"<h2>{s[group]}</h2>")
        label = f" ({s['printed']} {e_(e['printed_page_label'])})" \
            if e["printed_page_label"] else ""
        body.append(f"<blockquote>{e_(e['text'])}</blockquote>")
        body.append(f"<p class=ref>{e_(e['document_title'])} · {s['page']} {e['physical_page']}"
                    f"{label} · {e_(' › '.join(e['section_path']))} · "
                    f"<a href=\"{e_(e['source_url'])}\">{e_(e['source_url'])}</a></p>")
        if e["note"]:
            body.append(f"<p class=note>{NOTE_LABEL[lang]}: {e_(e['note'])}</p>")
    if brief.get("attachments"):
        body.append(f"<h2>{s['attachments']}</h2><ul>" + "".join(
            f"<li><a href=\"{e_(a['url'])}\">{e_(a['title'])}</a></li>"
            for a in brief["attachments"]) + "</ul>")
    if brief.get("unsearchable_pages"):
        body.append(f"<p class=meta>{s['unsearchable']}: "
                    f"{e_(', '.join(brief['unsearchable_pages']))}</p>")
    return (f"<!doctype html><html lang={lang}><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{e_(brief['case_no'])} brief</title><style>{_CSS}</style></head>"
            f"<body>{''.join(body)}</body></html>")
