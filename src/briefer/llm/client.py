"""LLM client wrapper: provider choice per stage, GDPR gate, JSON-schema validation with one
retry, token/cost budget, consecutive-failure counting, and the record/replay cache."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field

import jsonschema

from .. import paths
from .adapters import ADAPTERS
from .base import LLMError, LLMResult, Message, Usage

log = logging.getLogger(__name__)


class BudgetExceeded(RuntimeError):
    pass


class ProviderNotApproved(RuntimeError):
    pass


class ReplayMiss(LLMError):
    pass


@dataclass
class CallRecord:
    stage: str
    item: str | None
    model: str
    usage: Usage
    cached: bool
    ok: bool


@dataclass
class LLMClient:
    """One client per run. `mode` (BRIEFER_LLM_MODE):
    live   — always call the model, and store the answer for later replay;
    record — use a stored answer if there is one, else call the model and store it;
    replay — stored answers only; a miss is an error (deterministic, offline CI)."""

    real_documents: bool
    mode: str = field(default_factory=lambda: os.environ.get("BRIEFER_LLM_MODE", "record"))
    calls: list[CallRecord] = field(default_factory=list)
    consecutive_failures: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self.cfg = paths.config("llm")
        self.budget = paths.config("budget")
        if self.mode not in ("live", "record", "replay"):
            raise ValueError(f"BRIEFER_LLM_MODE must be live|record|replay, not {self.mode}")

    # -- accounting -------------------------------------------------------------------
    def tokens_used(self, item: str | None = None) -> int:
        return sum(c.usage.total for c in self.calls if item is None or c.item == item)

    def cost_usd(self) -> float:
        total = 0.0
        for c in self.calls:
            if c.cached:
                continue
            prov = self.cfg["providers"][self.cfg["stages"][c.stage]["provider"]]
            total += c.usage.total / 1e6 * prov.get("cost_per_mtok_usd", 0.0)
        return total

    def llm_calls(self, item: str) -> int:
        return sum(1 for c in self.calls if c.item == item)

    def _check_budget(self, item: str | None, max_tokens: int) -> None:
        if item and self.tokens_used(item) + max_tokens > self.budget["per_item_tokens"]:
            raise BudgetExceeded(f"item {item} token budget "
                                 f"({self.budget['per_item_tokens']}) exhausted")
        if self.tokens_used() + max_tokens > self.budget["per_run_tokens"]:
            raise BudgetExceeded(f"run token budget ({self.budget['per_run_tokens']}) exhausted")
        if self.cost_usd() > self.budget["per_run_usd"]:
            raise BudgetExceeded(f"run cost cap (${self.budget['per_run_usd']}) exceeded")

    # -- calling ----------------------------------------------------------------------
    def _stage(self, stage: str) -> tuple[dict, dict]:
        st = self.cfg["stages"][stage]
        prov = self.cfg["providers"][st["provider"]]
        if self.real_documents and not prov.get("gdpr_approved", False):
            raise ProviderNotApproved(
                f"provider '{st['provider']}' is not gdpr_approved; refusing real documents "
                f"(config/llm.yaml)")
        return st, prov

    def _key(self, model: str, messages: list[Message], schema: dict | None, st: dict) -> str:
        blob = json.dumps({"model": model, "messages": messages, "schema": schema,
                           "temperature": st.get("temperature"), "seed": st.get("seed")},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def _raw(self, stage: str, messages: list[Message], schema: dict | None,
             max_tokens: int) -> LLMResult:
        st, prov = self._stage(stage)
        key = self._key(st["model"], messages, schema, st)
        cache_file = paths.LLM_CACHE / key[:2] / f"{key}.json"
        if self.mode in ("record", "replay") and cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return LLMResult(text=data["text"], usage=Usage(**data["usage"]), cached=True)
        if self.mode == "replay":
            raise ReplayMiss(f"no recorded answer for {stage} call {key[:12]} (replay mode)")
        adapter = ADAPTERS[prov["adapter"]](**{**prov, "num_ctx": self.cfg.get("num_ctx", 8192)})
        result = adapter.complete(messages, schema, max_tokens, model=st["model"],
                                  temperature=st.get("temperature", 0.0), seed=st.get("seed"))
        if self.mode in ("record", "live"):  # live refreshes the cache that replay reads
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(
                {"stage": stage, "model": st["model"], "text": result.text,
                 "usage": {"input_tokens": result.usage.input_tokens,
                           "output_tokens": result.usage.output_tokens}},
                ensure_ascii=False), encoding="utf-8")
        return result

    def complete_json(self, stage: str, messages: list[Message], schema: dict, *,
                      item: str | None = None, max_tokens: int | None = None) -> dict:
        """Call the stage's model and return JSON validated against `schema`. One retry
        with the validation error appended; then LLMError."""
        st = self.cfg["stages"][stage]
        max_tokens = max_tokens or st.get("max_tokens", 1000)
        msgs = list(messages)
        last_err = ""
        for attempt in range(2):
            # Pre-check reserves the prompt (≈4 chars per token) plus the maximum output.
            est_input = sum(len(m["content"]) for m in msgs) // 4
            with self._lock:
                self._check_budget(item, max_tokens + est_input)
            ok = False
            try:
                res = self._raw(stage, msgs, schema, max_tokens)
            except ReplayMiss:
                raise
            except LLMError as e:
                last_err = str(e)
                with self._lock:
                    self.calls.append(CallRecord(stage, item, st["model"], Usage(), False, False))
                    self.consecutive_failures += 1
                continue
            try:
                data = json.loads(res.text)
                jsonschema.validate(data, schema)
                ok = True
            except (json.JSONDecodeError, jsonschema.ValidationError) as e:
                last_err = (e.msg if isinstance(e, json.JSONDecodeError) else e.message)[:300]
                msgs = messages + [
                    {"role": "assistant", "content": res.text[:2000]},
                    {"role": "user", "content": f"That was not valid: {last_err}. "
                                                "Answer again with JSON matching the schema."}]
            with self._lock:
                self.calls.append(CallRecord(stage, item, st["model"], res.usage, res.cached, ok))
                self.consecutive_failures = 0 if ok else self.consecutive_failures + 1
            if ok:
                return data
            log.warning("%s %s: invalid JSON (attempt %d): %s", stage, item, attempt + 1, last_err)
        raise LLMError(f"{stage} {item}: no valid JSON after retry: {last_err}")
