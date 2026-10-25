"""S3 — Personal-data screen (and injection-pattern flags).

Segments with a detected national ID number (with checksum), e-mail address or phone
number are flagged and excluded from the index, so they cannot reach a brief. A document
above the flagged-share threshold is rejected for review.

Person-name detection with a Norwegian NER model (§4.2) is not wired in yet: no NER model
is installed. `NAME_DETECTION` reports that state so it shows up in run logs.

Injection patterns are flagged but kept in the index: kill-switch condition 4 halts the run
if the agent selects a flagged segment.
"""

from __future__ import annotations

import logging
import re

from . import paths
from .models import ParsedDoc

log = logging.getLogger(__name__)

NAME_DETECTION = "disabled (no Norwegian NER model installed)"

_FNR = re.compile(r"(?<!\d)(\d{6})\s?(\d{5})(?!\d)")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_PHONE = re.compile(
    r"(?:\+47[\s-]?\d{2}\s?\d{2}\s?\d{2}\s?\d{2}"                      # +47 xx xx xx xx
    r"|(?i:tlf\.?|telefon|mobil|phone)[:\s]{1,3}\d{2}\s?\d{2}\s?\d{2}\s?\d{2}"
    r"|(?<!\d)[49]\d \d{2} \d{2} \d{2}(?!\d))"                          # 9x xx xx xx
)
INJECTION = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above|earlier) instructions"
    r"|disregard (?:all |the )?(?:previous|prior|above) (?:instructions|rules)"
    r"|ignorer (?:alle |tidligere |ovenstående )*instruksjon"
    r"|you are now\b|new instructions:|system prompt"
    r"|include all of (?:chapter|kapittel)",
    re.IGNORECASE,
)


def fnr_valid(digits: str) -> bool:
    """Norwegian national ID (fødselsnummer / D-nummer) with both mod-11 check digits."""
    if len(digits) != 11 or not digits.isdigit():
        return False
    d = [int(c) for c in digits]
    w1 = [3, 7, 6, 1, 8, 9, 4, 5, 2]
    w2 = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    k1 = 11 - sum(a * b for a, b in zip(w1, d[:9], strict=True)) % 11
    k1 = 0 if k1 == 11 else k1
    if k1 == 10 or k1 != d[9]:
        return False
    k2 = 11 - sum(a * b for a, b in zip(w2, d[:10], strict=True)) % 11
    k2 = 0 if k2 == 11 else k2
    return k2 != 10 and k2 == d[10]


def detect(text: str) -> list[str]:
    found = []
    if any(fnr_valid(a + b) for a, b in _FNR.findall(text)):
        found.append("pii:national_id")
    if _EMAIL.search(text):
        found.append("pii:email")
    if _PHONE.search(text):
        found.append("pii:phone")
    return found


def screen(doc: ParsedDoc) -> tuple[ParsedDoc, dict]:
    threshold = paths.config("privacy")["max_flagged_ratio"]
    counts: dict[str, int] = {}
    segments = []
    for s in doc.segments:
        flags = list(s.flags) + detect(s.text)
        if INJECTION.search(s.text):
            flags.append("injection")
        for f in flags:
            counts[f] = counts.get(f, 0) + 1
        segments.append(s.model_copy(update={"flags": flags}))
    flagged = sum(1 for s in segments if any(f.startswith("pii:") for f in s.flags))
    ratio = flagged / max(len(segments), 1)
    rejected = None
    if ratio > threshold:
        rejected = f"{flagged} of {len(segments)} segments contain personal data " \
                   f"({ratio:.1%} > {threshold:.0%}); document held for review"
        log.warning("S3 %s rejected: %s", doc.title, rejected)
    report = {"doc_id": doc.doc_id, "flag_counts": counts, "pii_segments": flagged,
              "pii_ratio": round(ratio, 4), "rejected": rejected,
              "name_detection": NAME_DETECTION}
    log.info("S3 %s: %s", doc.title, report)
    return doc.model_copy(update={"segments": segments, "rejected": rejected}), report


def indexable(seg) -> bool:
    return not any(f.startswith("pii:") for f in seg.flags)
