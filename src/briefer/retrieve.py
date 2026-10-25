"""S7 — Retrieve and expand.

Top-k per query, merged by reciprocal rank fusion, then expanded with cross-reference
targets, the sections the hits concentrate in, table headers (carried on table-row segments)
and neighbouring segments. Navigation pages (contents, index) are never candidates.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .index import Index
from .models import Segment, XRef

K_PER_QUERY = 8
TOP_MERGED = 18
NEIGHBOURS_FOR_TOP = 6
TOP_SECTIONS = 3            # sections with the highest summed score are expanded
PER_SECTION = 10            # segments taken from each, nearest to the hits first
MIN_CHARS = 15              # drop formula fragments such as "f2(n)" or "100"
MAX_CANDIDATES = 40
RRF_K = 60
NAVIGATION = {"contents", "table of contents", "innhold", "innhald", "innholdsfortegnelse",
              "index", "register", "stikkordregister", "list of boxes", "list of figures",
              "list of tables", "figurliste", "tabelliste"}


@dataclass
class Candidate:
    seg: Segment
    score: float
    via: str          # search | neighbour | section | cross_reference_from:<segment_id>

    @property
    def found_via(self) -> str:
        return self.via if self.via.startswith("cross_reference_from") else "search"


def _usable(seg: Segment) -> bool:
    root = seg.section_path[0].lower() if seg.section_path else ""
    return root not in NAVIGATION and len(seg.text) >= MIN_CHARS


def _seq_map(index: Index) -> dict[tuple[str, int], Segment]:
    m = getattr(index, "_seq_map", None)
    if m is None:
        m = {(s.doc_id, s.seq): s for s in index.segments}
        index._seq_map = m  # type: ignore[attr-defined]
    return m


def _neighbours(index: Index, seg: Segment) -> list[Segment]:
    seq_map = _seq_map(index)
    out = []
    for d in (-1, 1):
        n = seq_map.get((seg.doc_id, seg.seq + d))
        if n and n.section_path == seg.section_path:
            out.append(n)
    return out


def _sections(index: Index) -> dict[tuple[str, tuple[str, ...]], list[Segment]]:
    m = getattr(index, "_sections", None)
    if m is None:
        m = defaultdict(list)
        for s in index.segments:
            m[(s.doc_id, tuple(s.section_path))].append(s)
        index._sections = m  # type: ignore[attr-defined]
    return m


def retrieve(index: Index, queries: list[str], doc_ids: set[str],
             xrefs: dict[str, list[XRef]]) -> list[Candidate]:
    fused: dict[str, float] = {}
    for q in queries:
        hits = [(s, sc) for s, sc in index.search(q, K_PER_QUERY * 2, doc_ids) if _usable(s)]
        for rank, (seg, _) in enumerate(hits[:K_PER_QUERY]):
            fused[seg.id] = fused.get(seg.id, 0.0) + 1.0 / (RRF_K + rank)
    top = sorted(fused, key=fused.get, reverse=True)[:TOP_MERGED]
    cands: dict[str, Candidate] = {
        sid: Candidate(index.by_id[sid], fused[sid], "search") for sid in top}

    def add(seg: Segment, score: float, via: str) -> None:
        if seg.id not in cands and _usable(seg) and seg.doc_id in doc_ids:
            cands[seg.id] = Candidate(seg, score, via)

    # Section expansion: where do the hits concentrate?
    sec_score: dict[tuple[str, tuple[str, ...]], float] = defaultdict(float)
    hit_seqs: dict[tuple[str, tuple[str, ...]], list[int]] = defaultdict(list)
    for sid in top:
        s = index.by_id[sid]
        key = (s.doc_id, tuple(s.section_path))
        sec_score[key] += fused[sid]
        hit_seqs[key].append(s.seq)
    sections = _sections(index)
    for key in sorted(sec_score, key=sec_score.get, reverse=True)[:TOP_SECTIONS]:
        members = sorted(sections[key], key=lambda s: min(abs(s.seq - h) for h in hit_seqs[key]))
        for s in [m for m in members if _usable(m)][:PER_SECTION]:
            add(s, sec_score[key] * 0.4, "section")

    for i, sid in enumerate(top):
        for ref in xrefs.get(sid, []):
            for t in ref.targets:
                if t in index.by_id:
                    add(index.by_id[t], fused[sid] * 0.5, f"cross_reference_from:{sid}")
        if i < NEIGHBOURS_FOR_TOP:
            for n in _neighbours(index, index.by_id[sid]):
                add(n, fused[sid] * 0.3, "neighbour")

    ranked = sorted(cands.values(), key=lambda c: c.score, reverse=True)[:MAX_CANDIDATES]
    return sorted(ranked, key=lambda c: (c.seg.doc_id, c.seg.seq))
