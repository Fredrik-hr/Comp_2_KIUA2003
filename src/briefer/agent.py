"""S8 — Relevance agent (LLM, one per item).

A bounded tool loop (max 8 tool calls) over read-only tools: search_index, get_segment and
follow_reference. The agent returns segment IDs only; code copies the text (S9). IDs the
agent was never shown are rejected.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from .agenda import Item
from .index import Index
from .llm import LLMClient
from .models import XRef
from .paths import context_text
from .retrieve import Candidate
from .understand import describe

log = logging.getLogger(__name__)

MAX_TOOL_CALLS = 8
SNIPPET_CHARS = 450
LANG_NAME = {"nb": "Norwegian bokmål", "nn": "Norwegian nynorsk", "en": "English"}

# Length limits are part of the schema so constrained decoding (Ollama) cannot run away:
# small models otherwise repeat a query string until max_tokens (seen in the first run).
_ID = {"type": "string", "maxLength": 40}
_SELECTION = {
    "type": "object", "required": ["segment_id", "relevance", "note"],
    "properties": {
        "segment_id": _ID,
        "relevance": {"enum": ["direct", "supporting", "cross_reference"]},
        "note": {"type": "string", "maxLength": 160},
    },
}
STEP_SCHEMA = {
    "type": "object",
    "required": ["action"],
    "properties": {
        "action": {"enum": ["search_index", "get_segment", "follow_reference", "finish"]},
        "query": {"type": "string", "maxLength": 80},
        "segment_id": _ID,
        "nothing_found": {"type": "boolean"},
        "selections": {"type": "array", "maxItems": 20, "items": _SELECTION},
    },
}
FINISH_SCHEMA = {
    "type": "object",
    "required": ["action", "nothing_found", "selections"],
    "properties": {
        "action": {"enum": ["finish"]},
        "nothing_found": {"type": "boolean"},
        "selections": {"type": "array", "maxItems": 20, "items": _SELECTION},
    },
}

PROTOCOL = f"""You work in steps. Each reply is ONE JSON object with an "action":

- {{"action": "search_index", "query": "<keywords>"}} — search the item's documents again.
- {{"action": "get_segment", "segment_id": "<id>"}} — read one segment in full.
- {{"action": "follow_reference", "segment_id": "<id>"}} — get the segments that a segment's
  cross-references ("see Section 4.2", "jf. kap. 3") point to.
- {{"action": "finish", "nothing_found": false, "selections": [
     {{"segment_id": "<id>", "relevance": "direct|supporting|cross_reference",
      "note": "<one line>"}}]}}
- {{"action": "finish", "nothing_found": true, "selections": []}} — no candidate is about the item.

You may use at most {MAX_TOOL_CALLS} tool calls; finishing early is fine. Only use segment IDs
you have been shown. Never write document text yourself — only IDs and one-line notes."""


def _render(c: Candidate | None, seg, via: str | None = None) -> str:
    seg = c.seg if c else seg
    via = via or (c.via if c else "tool")
    tag = " [via xref]" if via.startswith("cross_reference_from") else ""
    text = seg.text if len(seg.text) <= SNIPPET_CHARS else seg.text[:SNIPPET_CHARS] + " …"
    section = " > ".join(seg.section_path[-2:]) or "-"
    return f"[{seg.id}] page {seg.page} | {section}{tag}\n{text}"


def _untrusted(body: str) -> str:
    return f"<untrusted_document_content>\n{body}\n</untrusted_document_content>"


@dataclass
class AgentResult:
    nothing_found: bool
    selections: list[dict]
    rejected_ids: list[str] = field(default_factory=list)
    tool_calls: int = 0
    trace: list[dict] = field(default_factory=list)
    found_via: dict[str, str] = field(default_factory=dict)


def run(item: Item, understanding: dict, candidates: list[Candidate], index: Index,
        xrefs: dict[str, list[XRef]], doc_ids: set[str], llm: LLMClient,
        brief_language: str) -> AgentResult:
    shown: dict[str, str] = {c.seg.id: c.found_via for c in candidates}
    system = "\n\n".join([
        "You select passages for a pre-meeting brief. Follow the rubric exactly.",
        context_text("relevance_rubric.md"), context_text("injection_policy.md"), PROTOCOL,
        f"Write every note in {LANG_NAME[brief_language]}, at most 15 words.",
    ])
    user = (f"Agenda item:\n{describe(item)}\n\nWhat it is about: {understanding['topic']}\n\n"
            f"Candidate segments ({len(candidates)}):\n"
            + _untrusted("\n\n".join(_render(c, None) for c in candidates))
            + "\n\nDecide. Reply with one JSON action.")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    result = AgentResult(nothing_found=False, selections=[])

    while True:
        forced = result.tool_calls >= MAX_TOOL_CALLS
        step = llm.complete_json("S8", messages, FINISH_SCHEMA if forced else STEP_SCHEMA,
                                 item=item.case_no)
        result.trace.append(step)
        action = step["action"]
        if action == "finish":
            break
        result.tool_calls += 1
        sid = step.get("segment_id", "")
        if action == "search_index":
            hits = index.search(step.get("query", ""), 6, doc_ids)
            for seg, _ in hits:
                shown.setdefault(seg.id, "search")
            body = "\n\n".join(_render(None, s, shown[s.id]) for s, _ in hits) or "(no results)"
        elif action == "get_segment":
            seg = index.by_id.get(sid) if sid in shown else None
            body = (f"[{seg.id}] page {seg.page} | {' > '.join(seg.section_path)}\n{seg.text}"
                    if seg else f"(unknown segment id {sid!r} — use an ID you were shown)")
        else:  # follow_reference
            refs = xrefs.get(sid, []) if sid in shown else []
            lines = []
            for ref in refs:
                for t in ref.targets:
                    if t in index.by_id:
                        shown.setdefault(t, f"cross_reference_from:{sid}")
                        lines.append(f"({ref.label})\n" + _render(None, index.by_id[t],
                                                                  shown[t]))
            body = "\n\n".join(lines) or f"(segment {sid!r} has no resolvable cross-references)"
        remaining = MAX_TOOL_CALLS - result.tool_calls
        messages += [
            {"role": "assistant", "content": _compact(step)},
            {"role": "user", "content": f"Tool result ({action}):\n" + _untrusted(body)
                + f"\n\n{remaining} tool calls left. Reply with one JSON action."},
        ]

    result.nothing_found = bool(step.get("nothing_found")) and not step.get("selections")
    seen = set()
    for sel in step.get("selections", []):
        sid = sel["segment_id"].strip().strip("[]")
        if sid not in shown or sid not in index.by_id:
            result.rejected_ids.append(sid)
            continue
        if sid in seen:
            continue
        seen.add(sid)
        result.selections.append({**sel, "segment_id": sid})
        result.found_via[sid] = shown[sid]
    if result.rejected_ids:
        log.warning("S8 %s: rejected unknown segment ids %s", item.case_no, result.rejected_ids)
    return result


POINTWISE_SCHEMA = {
    "type": "object",
    "required": ["relevance", "note"],
    "properties": {
        "relevance": {"enum": ["direct", "supporting", "cross_reference", "not_relevant"]},
        "note": {"type": "string", "maxLength": 160},
    },
}


def run_pointwise(item: Item, understanding: dict, candidates: list[Candidate],
                  llm: LLMClient, brief_language: str) -> AgentResult:
    """Alternative S8 strategy for small models: one call per candidate, same rubric.

    No tool loop; the candidate set from S7 (already expanded with cross-references and
    neighbours) is judged segment by segment. Selected via `stages.S8.strategy`."""
    system = "\n\n".join([
        "You judge whether ONE document segment belongs in a pre-meeting brief for ONE agenda "
        "item. Follow the rubric exactly. Answer `not_relevant` unless the segment is about "
        "the item's subject.",
        context_text("relevance_rubric.md"), context_text("injection_policy.md"),
        f"Write the note in {LANG_NAME[brief_language]}, at most 15 words.",
    ])
    head = f"Agenda item:\n{describe(item)}\n\nWhat it is about: {understanding['topic']}\n\n"
    result = AgentResult(nothing_found=False, selections=[])
    for c in candidates:
        user = head + "Segment:\n" + _untrusted(_render(c, None)) + "\n\nReturn the JSON object."
        out = llm.complete_json("S8", [{"role": "system", "content": system},
                                       {"role": "user", "content": user}],
                                POINTWISE_SCHEMA, item=item.case_no, max_tokens=200)
        result.trace.append({"segment_id": c.seg.id, **out})
        if out["relevance"] != "not_relevant":
            result.selections.append({"segment_id": c.seg.id, "relevance": out["relevance"],
                                      "note": out["note"]})
            result.found_via[c.seg.id] = c.found_via
    result.nothing_found = not result.selections
    return result


def _compact(step: dict) -> str:
    return json.dumps(step, ensure_ascii=False)
