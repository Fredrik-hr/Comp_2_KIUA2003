"""S7b — Find the proposed decision (innstilling) by code.

What the meeting is asked to decide is the first thing a participant needs, so it is not
left to the language model. In the case paper for an item, the first page has a header row
ending in the case number ("Fylkesutvalget 29.09.2026 93/26"), followed by a line or heading
"... innstilling til vedtak:" (or "Forslag til vedtak:") and the decision points. This module
returns those segments, verbatim, from the parsed document; the normal V1–V7 checks apply.

Nothing found is a valid result and is logged by the caller; the module never guesses.
"""

from __future__ import annotations

import re

from .models import ParsedDoc, Segment

DECISION = re.compile(r"(?:innstilling|forslag)\s+til\s+(?:vedtak|uttale|uttalelse)\s*:?",
                      re.IGNORECASE)
# Where the decision block ends: attachments list, the case presentation, or a new heading.
STOP = re.compile(r"^(?:vedlegg|saksopplysninger|saksframstilling|saksutgreiing|bakgrunn|"
                  r"sammendrag|samandrag|saken gjelder|innledning)\b", re.IGNORECASE)
MAX_SEGMENTS = 15
MAX_PAGES = 2          # the block may run onto the next page


def _number(case_no: str) -> str | None:
    m = re.search(r"\d{1,4}/\d{2,4}", case_no)
    return m.group(0) if m else None


def _usable(seg: Segment) -> bool:
    # Signatures ("<name> Fylkeskommunedirektør") are flagged pii:name by S3 and stop here.
    return not any(f.startswith("pii:") or f == "injection" for f in seg.flags)


def find(case_no: str, doc: ParsedDoc) -> list[Segment]:
    """The segments holding the proposed decision for `case_no` in `doc`, or []."""
    num = _number(case_no)
    if not num or doc.rejected:
        return []
    header = re.compile(rf"(?:^|\s){re.escape(num)}$")
    segs = doc.segments
    for i, anchor in enumerate(segs):
        if not header.search(anchor.text):
            continue
        out: list[Segment] = []
        started = False
        for seg in segs[i + 1:]:
            if seg.page > anchor.page + MAX_PAGES - 1:
                break
            if not started:
                m = DECISION.search(seg.text)
                if not m:
                    continue
                started = True
                rest = seg.text[m.end():].strip()
                if rest and seg.kind != "heading" and _usable(seg):
                    out.append(seg)      # decision text in the same segment as the label
                continue
            if not _usable(seg) or STOP.match(seg.text) or seg.kind == "heading":
                break
            out.append(seg)
            if len(out) >= MAX_SEGMENTS:
                break
        if started:
            return out
    return []
