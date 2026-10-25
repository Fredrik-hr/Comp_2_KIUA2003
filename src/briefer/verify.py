"""S10 — Verify. The hard correctness rules V1–V7 (§3.2).

V1–V5 are per extract; a failing extract is removed and logged, never shown. V6 checks the
whole brief against context/output_schema.json; V7 checks skipped items made no LLM calls.
Every check re-reads the source PDF; none trusts the parser's cached text.
"""

from __future__ import annotations

import json
import re
from functools import cache
from pathlib import Path
from urllib.parse import urlparse

import fitz
import httpx
import jsonschema

from . import paths
from .fetch import FetchError, resolve_local
from .models import Extract, ParsedDoc
from .parse import detect_label, page_text

# Norwegian and plain number formats: 1 234,5 · 12,3 % · 2027–2030 · 3.5 · 42
_NUMBER = re.compile(r"(?<![\w,.])\d{1,3}(?:[   ]\d{3})+(?:,\d+)?(?![\d])"
                     r"|(?<![\w])\d+(?:[.,]\d+)?(?![\d])")


def numbers(s: str) -> set[str]:
    return {re.sub(r"[   ]", "", m.group(0)) for m in _NUMBER.finditer(s)}


class SourceDocs:
    """Opens each source PDF once per verification run."""

    def __init__(self, docs: dict[str, tuple[ParsedDoc, Path]]) -> None:
        self.docs = docs
        self._open: dict[str, fitz.Document] = {}
        self._text: dict[tuple[str, int], str] = {}

    def pdf(self, doc_id: str) -> fitz.Document:
        if doc_id not in self._open:
            self._open[doc_id] = fitz.open(self.docs[doc_id][1])
        return self._open[doc_id]

    def page_text(self, doc_id: str, page: int) -> str:
        key = (doc_id, page)
        if key not in self._text:
            self._text[key] = page_text(self.pdf(doc_id)[page - 1])
        return self._text[key]


def v1_verbatim(e: Extract, src: SourceDocs, doc_id: str) -> str | None:
    if e.text not in src.page_text(doc_id, e.physical_page):
        return "V1 text is not a verbatim substring of the cited page"
    return None


def v2_figures(e: Extract, src: SourceDocs, doc_id: str) -> str | None:
    page_nums = numbers(src.page_text(doc_id, e.physical_page))
    missing = numbers(e.text) - page_nums
    if missing:
        return f"V2 numbers not on cited page: {sorted(missing)[:5]}"
    extra = numbers(e.note) - numbers(e.text)
    if extra:
        return f"V2 note introduces numbers not in its extract: {sorted(extra)[:5]}"
    return None


def v3_label(e: Extract, src: SourceDocs, doc_id: str) -> str | None:
    pdf = src.pdf(doc_id)
    label, _ = detect_label(pdf, pdf[e.physical_page - 1])
    if label != e.printed_page_label:
        return f"V3 printed label {e.printed_page_label!r} != page's label {label!r}"
    return None


def v4_section(e: Extract, src: SourceDocs, doc: ParsedDoc) -> str | None:
    off = src.page_text(doc.doc_id, e.physical_page).find(e.text)
    if off < 0:
        return "V4 cannot locate extract on page"
    pos = (e.physical_page, off)
    stack: list = []
    for h in doc.headings:
        if (h.page, h.offset) > pos:
            break
        while stack and stack[-1].level >= h.level:
            stack.pop()
        stack.append(h)
    actual = [h.text for h in stack]
    if actual != e.section_path:
        return f"V4 extract lies in {' > '.join(actual) or '(no section)'}, not the cited section"
    return None


@cache
def _url_ok(url: str) -> bool:
    if url.startswith("local:"):
        try:
            resolve_local(url)
            return True
        except FetchError:
            return False
    host = urlparse(url).hostname or ""
    allowed = paths.config("sources")["allowed_domains"]
    if not any(host == d or host.endswith("." + d) for d in allowed):
        return False
    try:
        return httpx.head(url, timeout=20, follow_redirects=True).status_code == 200
    except httpx.HTTPError:
        return False


def v5_link(e: Extract, doc: ParsedDoc) -> str | None:
    base, _, frag = e.source_url.partition("#")
    if frag != f"page={e.physical_page}":
        return f"V5 link fragment {frag!r} != page={e.physical_page}"
    if not 1 <= e.physical_page <= doc.page_count:
        return "V5 page outside document"
    if not _url_ok(base):
        return f"V5 source does not resolve: {base}"
    return None


def check_extract(e: Extract, src: SourceDocs) -> list[str]:
    doc_id = e.segment_id.split(":")[0]
    doc = src.docs[doc_id][0]
    fails = [v1_verbatim(e, src, doc_id)]
    if fails[0] is None:  # later checks need the text located on the page
        fails += [v2_figures(e, src, doc_id), v4_section(e, src, doc)]
    fails += [v3_label(e, src, doc_id), v5_link(e, doc)]
    return [f for f in fails if f]


def _note_only_v2(fails: list[str]) -> bool:
    return len(fails) == 1 and fails[0].startswith("V2 note")


@cache
def _schema() -> dict:
    return json.loads((paths.CONTEXT / "output_schema.json").read_text(encoding="utf-8"))


def v6_schema(brief: dict) -> str | None:
    try:
        jsonschema.validate(brief, _schema())
    except jsonschema.ValidationError as err:
        return f"V6 schema: {err.message[:200]} at {'/'.join(map(str, err.absolute_path))}"
    return None


def v7_skip(brief: dict, llm_calls: int) -> str | None:
    if brief["status"] == "skipped" and (llm_calls or brief["extracts"]):
        return f"V7 skipped item made {llm_calls} LLM calls / has extracts"
    return None


def verify(brief: dict, extracts: list[Extract], src: SourceDocs, llm_calls: int
           ) -> tuple[dict, int, int]:
    """Returns the brief with failing extracts removed, plus (checked, failed) counts."""
    kept, removed, notes_dropped = [], [], []
    for e in extracts:
        fails = check_extract(e, src)
        if _note_only_v2(fails):
            # The verbatim extract is sound; only the machine-written note added a number.
            # Drop the note (V2 then holds) and keep the extract.
            notes_dropped.append({"segment_id": e.segment_id, "failures": fails})
            e = e.model_copy(update={"note": ""})
            fails = check_extract(e, src)
        if fails:
            removed.append({"segment_id": e.segment_id, "failures": fails})
        else:
            kept.append(e)
    brief["extracts"] = [e.model_dump() for e in kept]
    checks = [f"V1-V5: {len(kept)}/{len(extracts)} extracts passed"]
    if notes_dropped:
        checks.append(f"V2: {len(notes_dropped)} machine notes dropped for adding numbers")
    brief["verification"] = {"all_passed": True, "checks": checks, "removed": removed,
                             "notes_dropped": notes_dropped}
    for f in (v7_skip(brief, llm_calls), v6_schema(brief)):
        if f:
            checks.append(f)
            brief["verification"]["all_passed"] = False
    if not any(c.startswith("V6") for c in checks):
        checks.append("V6 schema: passed")
    if brief["status"] == "skipped" and not any(c.startswith("V7") for c in checks):
        checks.append("V7 skip: passed (0 LLM calls)")
    return brief, len(extracts), len(removed)
