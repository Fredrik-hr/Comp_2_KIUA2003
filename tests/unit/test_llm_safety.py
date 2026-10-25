import json

import pytest

from briefer import paths, safety
from briefer.llm import BudgetExceeded, LLMClient, LLMError, ProviderNotApproved, adapters
from briefer.llm.base import LLMResult, Usage

SCHEMA = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}


class FakeAdapter:
    replies: list[str] = []
    calls = 0

    def __init__(self, **_):
        pass

    def complete(self, messages, json_schema, max_tokens, *, model, temperature, seed):
        FakeAdapter.calls += 1
        return LLMResult(FakeAdapter.replies.pop(0), Usage(100, 20))


@pytest.fixture
def fake(monkeypatch, tmp_data):
    FakeAdapter.calls = 0
    monkeypatch.setitem(adapters.ADAPTERS, "fake", FakeAdapter)
    cfg = {
        "providers": {"fake_ok": {"adapter": "fake", "gdpr_approved": True},
                      "fake_cloud": {"adapter": "fake", "gdpr_approved": False}},
        "stages": {"S6": {"provider": "fake_ok", "model": "m", "max_tokens": 50},
                   "S8": {"provider": "fake_cloud", "model": "m", "max_tokens": 50}},
    }
    # each fake call uses 120 tokens and reserves 50 + prompt: the third call no longer fits
    budget = {"per_item_tokens": 250, "per_run_tokens": 10000, "per_run_usd": 1.0}
    real = paths.config

    def config(name):
        return {"llm": cfg, "budget": budget}.get(name) or real(name)

    monkeypatch.setattr(paths, "config", config)
    return FakeAdapter


def test_valid_json_returned_and_cached(fake):
    fake.replies = ['{"ok": true}']
    c = LLMClient(real_documents=True, mode="record")
    msgs = [{"role": "user", "content": "x"}]
    assert c.complete_json("S6", msgs, SCHEMA, item="A") == {"ok": True}
    # record mode: same call is served from the cache, no second adapter call
    c2 = LLMClient(real_documents=True, mode="replay")
    assert c2.complete_json("S6", msgs, SCHEMA, item="A") == {"ok": True}
    assert fake.calls == 1


def test_replay_miss_is_an_error(fake):
    c = LLMClient(real_documents=True, mode="replay")
    with pytest.raises(LLMError, match="replay"):
        c.complete_json("S6", [{"role": "user", "content": "new"}], SCHEMA)


def test_invalid_json_retried_once_then_error(fake):
    fake.replies = ["not json", '{"ok": "yes"}']
    c = LLMClient(real_documents=True, mode="live")
    with pytest.raises(LLMError, match="after retry"):
        c.complete_json("S6", [{"role": "user", "content": "y"}], SCHEMA)
    assert fake.calls == 2 and c.consecutive_failures == 2


def test_retry_recovers(fake):
    fake.replies = ["{broken", json.dumps({"ok": False})]
    c = LLMClient(real_documents=True, mode="live")
    assert c.complete_json("S6", [{"role": "user", "content": "z"}], SCHEMA) == {"ok": False}
    assert c.consecutive_failures == 0


def test_gdpr_gate_refuses_unapproved_provider_for_real_documents(fake):
    with pytest.raises(ProviderNotApproved):
        LLMClient(real_documents=True, mode="live").complete_json(
            "S8", [{"role": "user", "content": "q"}], SCHEMA)
    fake.replies = ['{"ok": true}']
    assert LLMClient(real_documents=False, mode="live").complete_json(
        "S8", [{"role": "user", "content": "q"}], SCHEMA)  # synthetic tests are exempt


def test_budget_exceeded_stops_calls(fake):
    fake.replies = ['{"ok": true}'] * 5
    c = LLMClient(real_documents=True, mode="live")
    for i in range(2):
        c.complete_json("S6", [{"role": "user", "content": str(i)}], SCHEMA, item="A")
    with pytest.raises(BudgetExceeded):
        c.complete_json("S6", [{"role": "user", "content": "3"}], SCHEMA, item="A")


def test_kill_switch_conditions(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    safety.check_stop()
    (tmp_path / "STOP").write_text("")
    with pytest.raises(safety.KillSwitch) as e:
        safety.check_stop()
    assert e.value.condition == 5
    (tmp_path / "STOP").unlink()
    monkeypatch.setenv("BRIEFER_DISABLED", "1")
    with pytest.raises(safety.KillSwitch):
        safety.check_stop()
    with pytest.raises(safety.KillSwitch) as e:
        safety.check_failed_ratio(10, 3)
    assert e.value.condition == 1
    safety.check_failed_ratio(10, 2)
    safety.check_failed_ratio(2, 2)  # too few extracts to judge
    with pytest.raises(safety.KillSwitch):
        safety.check_llm_failures(3)
    with pytest.raises(safety.KillSwitch) as e:
        safety.check_injection({"doc:p1:s1": ["injection"]})
    assert e.value.condition == 4
