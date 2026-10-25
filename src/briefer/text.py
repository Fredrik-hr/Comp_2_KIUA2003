"""The documented normalisation used by V1 and by the parser (§3.2).

NFC, ligatures expanded, soft hyphens removed, line-break hyphenation joined,
whitespace collapsed. Parser, verifier and labelling helper all use this function,
so an extract and its page are compared on equal terms.
"""

from __future__ import annotations

import re
import unicodedata

LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}
_HYPHEN_BREAK = re.compile(r"(\w)-[ \t]*\n\s*(\w)")
_WS = re.compile(r"\s+")


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    for lig, rep in LIGATURES.items():
        s = s.replace(lig, rep)
    s = s.replace("­", "")
    s = _HYPHEN_BREAK.sub(r"\1\2", s)
    return _WS.sub(" ", s).strip()


_TOKEN = re.compile(r"[a-zæøåäöü0-9]+(?:[-'][a-zæøåäöü0-9]+)*", re.IGNORECASE)

STOPWORDS = frozenset(
    """a an and are as at be by for from has have in is it its of on or that the this to was
    were which with we can if then than so not no also into our one two such these those
    og i på til av for med som er det en et den de om ved fra har skal blir vil kan ikkje ikke
    ein eit dei frå vert vere""".split()
)


def tokenize(s: str) -> list[str]:
    return [t for t in (m.group(0).lower() for m in _TOKEN.finditer(s)) if t not in STOPWORDS]
