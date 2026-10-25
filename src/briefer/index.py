"""S4 — Index.

One BM25 index per meeting over all indexable segments of all its documents. Segments
flagged with personal data (S3) are never indexed. Dense embeddings (the "hybrid" half
of §4.2) are not included yet; see README "Status".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi

from .models import ParsedDoc, Segment
from .privacy import indexable
from .text import tokenize


@dataclass
class Index:
    segments: list[Segment]
    by_id: dict[str, Segment] = field(init=False)
    _bm25: BM25Okapi | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.by_id = {s.id: s for s in self.segments}
        corpus = [tokenize(" ".join(s.section_path[-1:]) + " " + s.text) for s in self.segments]
        if any(corpus):
            self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int = 10, doc_ids: set[str] | None = None
               ) -> list[tuple[Segment, float]]:
        toks = tokenize(query)
        if not toks or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(toks)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in ranked:
            if scores[i] <= 0:
                break
            seg = self.segments[i]
            if doc_ids is not None and seg.doc_id not in doc_ids:
                continue
            out.append((seg, float(scores[i])))
            if len(out) == k:
                break
        return out


def build(docs: list[ParsedDoc]) -> Index:
    segs = [s for d in docs if not d.rejected for s in d.segments
            if indexable(s) and s.kind != "heading"]
    return Index(segs)
