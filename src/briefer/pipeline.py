"""Runs S0–S10 for one agenda file and stops at "awaiting review". Nothing is shared."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from . import agent, assemble, index, paths, privacy, retrieve, safety, understand, verify, xref
from .agenda import Agenda, Item, gate, load
from .fetch import Fetcher, FetchError
from .llm import BudgetExceeded, LLMClient, LLMError, ProviderNotApproved
from .models import ParsedDoc
from .parse import ParseError, parse_cached

log = logging.getLogger(__name__)
ITEM_WORKERS = 2


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


@dataclass
class RunLog:
    path: Path
    run_id: str
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __call__(self, stage: str, event: str, case_no: str | None = None, **data) -> None:
        rec = {"t": dt.datetime.now().isoformat(timespec="milliseconds"), "run_id": self.run_id,
               "stage": stage, "case_no": case_no, "event": event, **data}
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


@dataclass
class Shared:
    """Run-wide state the kill switch looks at."""
    checked: int = 0
    failed: int = 0
    halted: safety.KillSwitch | None = None
    budget_hit: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)


def _base_brief(item: Item, meeting_id: str, run_id: str, lang: str, style: str) -> dict:
    return {
        "case_no": item.case_no, "title": item.title, "meeting_id": meeting_id,
        "status": "draft", "skip_reason": None, "brief_language": lang, "agenda_style": style,
        "attachments": [{"title": a.title, "url": a.url} for a in item.attachments],
        "unsearchable_pages": [], "extracts": [],
        "verification": {"all_passed": True, "checks": []}, "llm_calls": 0, "tokens": 0,
        "run_id": run_id, "disclaimer": assemble.DISCLAIMER[lang],
    }


def run(agenda_path: Path, brief_language: str = "nb", style: str = "described",
        run_id: str | None = None, out_root: Path | None = None) -> dict:
    t0 = time.time()
    run_id = run_id or dt.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    safety.check_stop()
    agenda: Agenda = load(agenda_path)  # S0 (raises AgendaError)
    meeting = agenda.meeting
    out_dir = (out_root or paths.RUNS) / run_id / slug(meeting.id) / style
    out_dir.mkdir(parents=True, exist_ok=True)
    rlog = RunLog(out_dir / "run_log.jsonl", run_id)
    llm = LLMClient(real_documents=not meeting.synthetic)
    rlog("S0", "loaded", meeting=meeting.id, items=len(agenda.items), style=style,
         llm_mode=llm.mode, name_detection=privacy.NAME_DETECTION)

    gates = [gate(i.titles_only() if style == "titles_only" else i) for i in agenda.items]
    for g in gates:
        if not g.process:
            rlog("S0", "skipped", g.item.case_no, reason=g.skip_reason)

    # S1–S5: each document once per meeting, isolated per document.
    fetcher = Fetcher()
    docs: dict[str, ParsedDoc] = {}
    doc_paths: dict[str, Path] = {}
    url_to_doc: dict[str, str] = {}
    att_status: dict[str, str] = {}
    titles = {a.url: a.title for g in gates if g.process for a in g.item.attachments}
    for url, title in titles.items():
        safety.check_stop()
        try:
            f = fetcher.get(url)
            rlog("S1", "fetched", url=url, sha256=f.sha256)
            if f.doc_id not in docs:
                d = parse_cached(f.path, f.sha256, url, title)
                rlog("S2", "parsed", doc_id=d.doc_id, pages=d.page_count,
                     segments=len(d.segments), headings=len(d.headings),
                     no_text_layer=[p.page for p in d.pages if not p.has_text_layer],
                     hidden_chars_removed=sum(p.hidden_chars_removed for p in d.pages))
                d, report = privacy.screen(d)
                rlog("S3", "screened", **report)
                docs[d.doc_id] = d
                doc_paths[d.doc_id] = f.path
            url_to_doc[url] = f.doc_id
            att_status[url] = "rejected: " + docs[f.doc_id].rejected \
                if docs[f.doc_id].rejected else "ok"
        except (FetchError, ParseError) as e:
            att_status[url] = f"unreadable: {e}"
            rlog("S1/S2", "document_failed", url=url, error=str(e))
    safety.check_stop()
    idx = index.build(list(docs.values()))
    rlog("S4", "indexed", segments=len(idx.segments))
    refs = {d.doc_id: xref.build(d) for d in docs.values()}
    xgraph = xref.graph([r for rs in refs.values() for r in rs])
    rlog("S5", "xrefs", count=sum(len(r) for r in refs.values()),
         by_kind={k: sum(1 for rs in refs.values() for r in rs if r.kind == k)
                  for k in ("section", "chapter", "figure", "table", "page", "exercise",
                            "appendix")})
    src = verify.SourceDocs({k: (docs[k], doc_paths[k]) for k in docs})
    shared = Shared()

    def process(g) -> dict:
        item = g.item
        brief = _base_brief(item, meeting.id, run_id, brief_language, style)
        for a in brief["attachments"]:
            a["status"] = att_status.get(a["url"], "not fetched")
        if not g.process:
            brief.update(status="skipped", skip_reason=g.skip_reason)
            brief, _, _ = verify.verify(brief, [], src, llm.llm_calls(item.case_no))
            return brief
        if shared.halted:
            brief.update(status="halted", skip_reason=str(shared.halted))
            return brief
        if shared.budget_hit:
            brief.update(status="draft_incomplete", skip_reason=shared.budget_hit)
            return brief
        doc_ids = {url_to_doc[a.url] for a in item.attachments
                   if a.url in url_to_doc and not docs[url_to_doc[a.url]].rejected}
        brief["unsearchable_pages"] = [
            f"{docs[d].title} p.{p.page}" for d in doc_ids for p in docs[d].pages
            if not p.has_text_layer]
        try:
            safety.check_stop()
            if not doc_ids:
                brief["status"] = "nothing_found"
                rlog("S7", "no_searchable_documents", item.case_no)
                brief, _, _ = verify.verify(brief, [], src, llm.llm_calls(item.case_no))
                return brief
            und = understand.understand(item, llm)
            rlog("S6", "understood", item.case_no, **und)
            safety.check_llm_failures(llm.consecutive_failures)
            queries = [q["text"] for q in und["queries"]] + und.get("key_terms", [])[:4]
            cands = retrieve.retrieve(idx, queries, doc_ids, xgraph)
            rlog("S7", "candidates", item.case_no,
                 candidates=[{"id": c.seg.id, "via": c.via, "score": round(c.score, 4)}
                             for c in cands])
            safety.check_stop()
            if paths.config("llm")["stages"]["S8"].get("strategy", "agent") == "pointwise":
                res = agent.run_pointwise(item, und, cands, llm, brief_language)
            else:
                res = agent.run(item, und, cands, idx, xgraph, doc_ids, llm, brief_language)
            rlog("S8", "selected", item.case_no, nothing_found=res.nothing_found,
                 selections=res.selections, rejected_ids=res.rejected_ids,
                 tool_calls=res.tool_calls, trace=res.trace)
            safety.check_llm_failures(llm.consecutive_failures)
            safety.check_injection({s["segment_id"]: idx.by_id[s["segment_id"]].flags
                                    for s in res.selections})
            extracts = []
            for sel in res.selections:
                seg = idx.by_id[sel["segment_id"]]
                extracts.append(assemble.extract_for(
                    seg, docs[seg.doc_id], sel["relevance"], res.found_via[seg.id], sel["note"]))
            extracts = assemble.order(extracts, {s.id: s.seq for s in idx.segments})
            brief["llm_calls"] = llm.llm_calls(item.case_no)
            brief["tokens"] = llm.tokens_used(item.case_no)
            brief, checked, failed = verify.verify(brief, extracts, src, brief["llm_calls"])
            rlog("S10", "verified", item.case_no, checked=checked, failed=failed,
                 removed=brief["verification"]["removed"])
            with shared.lock:
                shared.checked += checked
                shared.failed += failed
                safety.check_failed_ratio(shared.checked, shared.failed)
            if brief["extracts"]:
                brief["status"] = "awaiting_review"
            elif extracts:
                brief["status"] = "draft_incomplete"
                brief["skip_reason"] = "all selected extracts failed verification"
            else:
                brief["status"] = "nothing_found"
        except safety.KillSwitch as k:
            with shared.lock:
                shared.halted = shared.halted or k
            brief.update(status="halted", skip_reason=str(k))
            rlog("KILL", "halted", item.case_no, condition=k.condition, reason=k.reason)
        except BudgetExceeded as b:
            with shared.lock:
                shared.budget_hit = str(b)
            brief.update(status="draft_incomplete", skip_reason=str(b))
            rlog("BUDGET", "exceeded", item.case_no, reason=str(b))
        except ProviderNotApproved as p:
            brief.update(status="halted", skip_reason=str(p))
            rlog("GDPR", "refused", item.case_no, reason=str(p))
        except LLMError as e:
            brief.update(status="draft_incomplete", skip_reason=f"LLM failure: {e}")
            rlog("LLM", "failed", item.case_no, error=str(e))
        brief["llm_calls"] = llm.llm_calls(item.case_no)
        brief["tokens"] = llm.tokens_used(item.case_no)
        return brief

    with ThreadPoolExecutor(max_workers=ITEM_WORKERS) as pool:
        briefs = list(pool.map(process, gates))

    for b in briefs:
        stem = out_dir / slug(b["case_no"])
        stem.with_suffix(".json").write_text(json.dumps(b, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
        stem.with_suffix(".md").write_text(assemble.to_markdown(b), encoding="utf-8")
        stem.with_suffix(".html").write_text(assemble.to_html(b), encoding="utf-8")
    summary = {
        "run_id": run_id, "meeting_id": meeting.id, "agenda": str(agenda_path), "style": style,
        "brief_language": brief_language, "llm_mode": llm.mode,
        "halted": str(shared.halted) if shared.halted else None,
        "budget_exceeded": shared.budget_hit,
        "statuses": {b["case_no"]: b["status"] for b in briefs},
        "extracts_checked": shared.checked, "extracts_failed": shared.failed,
        "llm_calls": len(llm.calls), "tokens": llm.tokens_used(),
        "cost_usd": round(llm.cost_usd(), 4), "seconds": round(time.time() - t0, 1),
        "documents": {d.doc_id: {"title": d.title, "url": d.url, "path": str(doc_paths[d.doc_id]),
                                 "pages": d.page_count} for d in docs.values()},
        "out_dir": str(out_dir),
    }
    (out_dir / "run.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    rlog("RUN", "finished", **{k: summary[k] for k in ("statuses", "tokens", "seconds")})
    return summary
