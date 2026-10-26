"""S3 — Personal-data screen (and injection-pattern flags).

Segments with a detected national ID number (with checksum), e-mail address or phone
number are flagged and excluded from the index, so they cannot reach a brief. A document
above the flagged-share threshold is rejected for review.

Person names are caught by rules for the fixed blocks of case papers (header fields,
signatures, letter closings; `name_rules` in config/privacy.yaml). Names in running text
are not detected: no Norwegian NER model is installed (§4.2). `NAME_DETECTION` reports
that state so it shows up in run logs.

Injection patterns are flagged but kept in the index: kill-switch condition 4 halts the run
if the agent selects a flagged segment.
"""

from __future__ import annotations

import logging
import re

from . import paths
from .models import ParsedDoc

log = logging.getLogger(__name__)

NAME_DETECTION = "rules only (header fields, signatures, closings); no NER for running text"

_CAP = r"[A-ZÆØÅ][a-zæøåäöüé]+(?:-[A-ZÆØÅ][a-zæøåäöüé]+)?"

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


class NameRules:
    """Rule-based person-name screen for header fields and signature blocks."""

    def __init__(self, cfg: dict) -> None:
        self.max_words = cfg["max_words"]
        labels = "|".join(re.escape(x) for x in cfg["field_labels"])
        self.field = re.compile(rf"^(?:{labels})\s*:\s*\S", re.IGNORECASE)
        self.roles = {r.lower() for r in cfg["roles"]}
        self.closings = tuple(c.lower() for c in cfg["closings"])
        self.not_names = {w.lower() for w in cfg["not_names"]} | {
            w for r in self.roles for w in r.split()}
        self.trailing = re.compile(rf"[.!?]\s+({_CAP}(?:\s+{_CAP}){{1,2}})$")
        credits = "|".join(re.escape(x) for x in cfg["credit_labels"])
        self.credit = re.compile(rf"\b(?:{credits})\s*:\s*{_CAP}\s+{_CAP}")

    def _is_name_word(self, w: str) -> bool:
        return re.fullmatch(_CAP, w) is not None and w.lower() not in self.not_names

    def _has_name_run(self, words: list[str]) -> bool:
        run = 0
        for w in words:
            run = run + 1 if self._is_name_word(w) else 0
            if run >= 2:
                return True
        return False

    def _has_role(self, text: str) -> bool:
        low = " " + " ".join(re.findall(r"[\wæøåÆØÅ]+", text.lower())) + " "
        return any(f" {r} " in low for r in self.roles)

    def is_name(self, text: str, previous: str | None) -> bool:
        words = [w.strip(",;()") for w in text.split()]
        short = len(words) <= self.max_words
        if self.field.match(text) or self.credit.search(text):
            return True
        if short and self._has_role(text) and self._has_name_run(words):
            return True
        if short and previous and previous.lower().rstrip(" ,!").endswith(self.closings) \
                and self._has_name_run(words):
            return True
        # names are short words; long compounds ("Generalistkommuneutvalget") cut by a
        # page break are not
        m = self.trailing.search(text)
        return bool(m) and all(self._is_name_word(w) and len(w) <= 15
                               for w in m.group(1).split())


def screen(doc: ParsedDoc) -> tuple[ParsedDoc, dict]:
    cfg = paths.config("privacy")
    threshold = cfg["max_flagged_ratio"]
    names = NameRules(cfg["name_rules"])
    counts: dict[str, int] = {}
    segments = []
    prev = None
    for s in doc.segments:
        flags = list(s.flags) + detect(s.text)
        before = prev.text if prev is not None and prev.page == s.page else None
        if names.is_name(s.text, before):
            flags.append("pii:name")
        prev = s
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
