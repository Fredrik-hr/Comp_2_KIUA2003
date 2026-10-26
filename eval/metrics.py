"""Recall / precision against gold labels (§3.3), plus inter-annotator agreement.

Unit: a segment. A gold passage counts as found if ≥50% of its characters fall inside the
selected extracts on the same page. A selected extract is correct if it overlaps any gold
passage of the same item.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from briefer.fetch import fetch  # noqa: E402
from briefer.parse import page_text  # noqa: E402

FOUND_SHARE = 0.5


@cache
def _doc(url: str) -> fitz.Document:
    return fitz.open(fetch(url).path)


@cache
def _page(url: str, page: int) -> str:
    return page_text(_doc(url)[page - 1])


def _span(url: str, page: int, text: str) -> tuple[int, int] | None:
    off = _page(url, page).find(text)
    return (off, off + len(text)) if off >= 0 else None


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def _by_topic(found: list[dict], passages: list[dict]) -> dict[str, list[int]]:
    """[found, total] per subtopic tag; a passage with several tags counts once for each."""
    out: dict[str, list[int]] = {}
    for g in passages:
        for t in g.get("topics", []):
            out.setdefault(t, [0, 0])[1] += 1
    for g in found:
        for t in g.get("topics", []):
            out[t][0] += 1
    return out


def score_item(brief: dict, gold: dict) -> dict:
    expect = gold.get("expect", "passages")
    status = brief["status"]
    out = {"case_no": brief["case_no"], "expect": expect, "status": status,
           "n_gold": 0, "n_selected": len(brief["extracts"])}
    if expect == "skipped":
        out["correct"] = status == "skipped" and brief.get("llm_calls", 0) == 0
        return out
    if expect == "nothing_found":
        out["correct"] = status == "nothing_found"
        out["false_positives"] = [e["segment_id"] for e in brief["extracts"]]
        return out

    passages = gold.get("passages", [])
    sel = []
    for e in brief["extracts"]:
        url = e["source_url"].split("#")[0]
        sel.append((e, url, _span(url, e["physical_page"], e["text"])))
    found, missed, gold_spans = [], [], []
    for g in passages:
        gs = _span(g["document"], g["physical_page"], g["quote"])
        gold_spans.append((g, gs))
        covered = 0
        if gs:
            # union of selected spans on this page, clipped to the gold span
            pts = sorted((max(s[0], gs[0]), min(s[1], gs[1])) for e, u, s in sel
                         if s and u == g["document"] and e["physical_page"] == g["physical_page"]
                         and _overlap(s, gs) > 0)
            end = gs[0]
            for a, b in pts:
                a = max(a, end)
                if b > a:
                    covered += b - a
                    end = b
        (found if gs and covered >= FOUND_SHARE * (gs[1] - gs[0]) else missed).append(g)
    correct_sel, wrong_sel = [], []
    for e, u, s in sel:
        hit = s and any(gs and g["document"] == u and g["physical_page"] == e["physical_page"]
                        and _overlap(s, gs) > 0 for g, gs in gold_spans)
        (correct_sel if hit else wrong_sel).append(e)
    out.update(
        n_gold=len(passages), n_found=len(found),
        recall=len(found) / len(passages) if passages else None,
        precision=len(correct_sel) / len(sel) if sel else None,
        found_by_via={v: [sum(1 for g in found if g.get("via") == v),
                          sum(1 for g in passages if g.get("via") == v)]
                      for v in ("search", "cross_reference")},
        found_by_topic=_by_topic(found, passages),
        selected_by_found_via={
            "search": [sum(1 for e in correct_sel if e["found_via"] == "search"),
                       sum(1 for e, _, _ in sel if e["found_via"] == "search")],
            "cross_reference": [
                sum(1 for e in correct_sel if e["found_via"] != "search"),
                sum(1 for e, _, _ in sel if e["found_via"] != "search")]},
        missed=[{"page": g["physical_page"], "quote": g["quote"][:120],
                 "topics": g.get("topics", [])} for g in missed],
        false_positives=[{"segment_id": e["segment_id"], "page": e["physical_page"],
                          "text": e["text"][:120]} for e in wrong_sel],
    )
    out["correct"] = status == "awaiting_review"
    return out


def aggregate(rows: list[dict]) -> dict:
    p_rows = [r for r in rows if r["expect"] == "passages"]
    gold = sum(r["n_gold"] for r in p_rows)
    found = sum(r.get("n_found", 0) for r in p_rows)
    sel = sum(r["n_selected"] for r in p_rows)
    corr = sum(round((r.get("precision") or 0) * r["n_selected"]) for r in p_rows)
    recalls = [r["recall"] for r in p_rows if r.get("recall") is not None]
    precs = [r["precision"] for r in p_rows if r.get("precision") is not None]
    micro_r = found / gold if gold else None
    micro_p = corr / sel if sel else None
    f1 = (2 * micro_r * micro_p / (micro_r + micro_p)) if micro_r and micro_p else 0.0
    xr = [sum(r["found_by_via"]["cross_reference"][i] for r in p_rows) for i in (0, 1)]
    by_topic: dict[str, list[int]] = {}
    for r in p_rows:
        for t, (f, n) in r.get("found_by_topic", {}).items():
            acc = by_topic.setdefault(t, [0, 0])
            acc[0] += f
            acc[1] += n
    return {
        "items": len(rows),
        "recall_micro": micro_r, "precision_micro": micro_p, "f1_micro": f1,
        "recall_macro": sum(recalls) / len(recalls) if recalls else None,
        "precision_macro": sum(precs) / len(precs) if precs else None,
        "gold_passages": gold, "found": found, "selected": sel,
        "recall_cross_reference_gold": xr[1] and xr[0] / xr[1],
        "found_by_topic": by_topic,
        "skip_correct": [sum(r["correct"] for r in rows if r["expect"] == "skipped"),
                         sum(1 for r in rows if r["expect"] == "skipped")],
        "reject_correct": [sum(r["correct"] for r in rows if r["expect"] == "nothing_found"),
                           sum(1 for r in rows if r["expect"] == "nothing_found")],
    }


def agreement(a: dict, b: dict, agenda: Path) -> str:
    """Segment-level F1 and Cohen's kappa between two annotators' labels."""
    from briefer.agenda import load
    from briefer.parse import parse_cached

    ag = load(agenda)
    segs = {}
    for url in {x.url for i in ag.items for x in i.attachments}:
        f = fetch(url)
        d = parse_cached(f.path, f.sha256, url, url)
        for s in d.segments:
            segs.setdefault((url, s.page), []).append(s)

    def to_segments(labels: dict) -> set[tuple[str, str]]:
        out = set()
        for case, item in labels["items"].items():
            for g in item.get("passages", []):
                gs = _span(g["document"], g["physical_page"], g["quote"])
                for s in segs.get((g["document"], g["physical_page"]), []):
                    ss = _span(g["document"], g["physical_page"], s.text)
                    if gs and ss and _overlap(gs, ss) > 0:
                        out.add((case, s.id))
        return out

    sa, sb = to_segments(a), to_segments(b)
    tp = len(sa & sb)
    f1 = 2 * tp / (len(sa) + len(sb)) if sa or sb else 1.0
    # universe: every segment on any page either annotator labelled, per case
    universe = set()
    for labels in (a, b):
        for case, item in labels["items"].items():
            for g in item.get("passages", []):
                for s in segs.get((g["document"], g["physical_page"]), []):
                    universe.add((case, s.id))
    n = len(universe) or 1
    po = sum(1 for u in universe if (u in sa) == (u in sb)) / n
    pa, pb = len(sa) / n, len(sb) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    return f"segments A={len(sa)} B={len(sb)} both={tp}  F1={f1:.3f}  kappa={kappa:.3f}"
