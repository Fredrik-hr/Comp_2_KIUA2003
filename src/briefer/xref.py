"""S5 — Cross-reference graph.

Detects references such as "jf. kap. 4.2", "se tabell 3", "vedlegg 2", "side 45" (and the
English "Section 4.2", "Figure 3.8", "page 100", "Chapter 8", "Exercise 2.3") and links the
referring segment to the segments it points to. Resolution is by code only; the LLM
fallback in §4.2 is not used.
"""

from __future__ import annotations

import re
from collections import defaultdict

from .models import ParsedDoc, Segment, XRef

TARGETS_PER_REF = 3

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("section", re.compile(
        r"\b(?:[Ss]ection|[Ss]ections|§|jf\.\s*kap(?:ittel|\.)?|kap(?:ittel|\.)|punkt)\s*"
        r"(\d+\.\d+(?:\.\d+)*)")),
    ("chapter", re.compile(
        r"\b(?:[Cc]hapter|jf\.\s*kap(?:ittel|\.)?|[Kk]apittel)\s*(\d+)\b(?!\.\d)")),
    ("figure", re.compile(r"\b(?:[Ff]igure|[Ff]igur|[Ff]ig\.)\s*(\d+\.\d+|\d+)")),
    ("table", re.compile(r"\b(?:[Tt]able|[Tt]abell)\s*(\d+\.\d+|\d+)")),
    ("exercise", re.compile(r"\b[Ee]xercises?\s*(\d+\.\d+)")),
    ("page", re.compile(r"\b(?:on |see |at )?(?:[Pp]age|[Ss]ide|s\.)\s*(\d{1,4})\b")),
    ("appendix", re.compile(r"\b(?:[Vv]edlegg|[Aa]ppendix)\s*(\d+|[A-Z])\b")),
]


def _first_body_after(doc: ParsedDoc, seq: int, n: int) -> list[Segment]:
    out = []
    for s in doc.segments[seq + 1:]:
        if s.kind == "heading":
            if out:
                break
            continue
        out.append(s)
        if len(out) == n:
            break
    return out


def _resolve(doc: ParsedDoc, kind: str, key: str) -> list[str]:
    if kind in ("section", "chapter"):
        for h in doc.headings:
            if h.number == key and (kind == "section" or h.level == 1 or "." not in key):
                return [s.id for s in _first_body_after(doc, h.seq, TARGETS_PER_REF)]
        return []
    if kind in ("figure", "table"):
        word = r"(?:Figure|Figur)" if kind == "figure" else r"(?:Table|Tabell)"
        pat = re.compile(rf"^{word}\s+{re.escape(key)}\b")
        hits = [s for s in doc.segments if s.kind == "caption" and pat.match(s.text)]
        if hits:
            nxt = _first_body_after(doc, hits[0].seq - 1, 2)
            return [hits[0].id] + [s.id for s in nxt if s.id != hits[0].id][:1]
        return []
    if kind == "exercise":
        pat = re.compile(rf"^{re.escape(key)}\.\s")
        return [s.id for s in doc.segments if pat.match(s.text)][:1]
    if kind == "page":
        pages = [p.page for p in doc.pages if p.label == key]
        if not pages:
            return []
        return [s.id for s in doc.segments if s.page == pages[0] and s.kind != "heading"
                ][:TARGETS_PER_REF]
    if kind == "appendix":
        for h in doc.headings:
            if re.match(rf"^(Vedlegg|Appendix)\s+{re.escape(key)}\b", h.text, re.I):
                return [s.id for s in _first_body_after(doc, h.seq, TARGETS_PER_REF)]
    return []


def build(doc: ParsedDoc) -> list[XRef]:
    refs: list[XRef] = []
    for seg in doc.segments:
        if seg.kind == "heading":
            continue
        seen = set()
        for kind, pat in _PATTERNS:
            for m in pat.finditer(seg.text):
                key = m.group(1)
                if (kind, key) in seen:
                    continue
                seen.add((kind, key))
                targets = [t for t in _resolve(doc, kind, key) if t != seg.id]
                if targets:
                    refs.append(XRef(source=seg.id, kind=kind, label=m.group(0).strip(),
                                     targets=targets))
    return refs


def graph(refs: list[XRef]) -> dict[str, list[XRef]]:
    g: dict[str, list[XRef]] = defaultdict(list)
    for r in refs:
        g[r.source].append(r)
    return dict(g)
