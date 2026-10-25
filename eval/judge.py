"""LLM-as-judge for machine-written notes (§6.3). Uses the `judge` stage in config/llm.yaml."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from briefer.llm import LLMClient, LLMError  # noqa: E402

PROMPT = (ROOT / "eval" / "judge_prompt.md").read_text(encoding="utf-8")
SCHEMA = {
    "type": "object", "required": ["faithful", "usefulness", "reason"],
    "properties": {"faithful": {"type": "boolean"},
                   "usefulness": {"type": "integer", "minimum": 1, "maximum": 3},
                   "reason": {"type": "string", "maxLength": 200}},
}


def judge_run(out_dir: Path) -> dict:
    llm = LLMClient(real_documents=False)
    judged = []
    for f in sorted(out_dir.glob("*.json")):
        if f.name == "run.json":
            continue
        brief = json.loads(f.read_text(encoding="utf-8"))
        for e in brief["extracts"]:
            if not e["note"]:
                continue
            msgs = [{"role": "system", "content": PROMPT},
                    {"role": "user", "content": f"EXTRACT:\n{e['text'][:1500]}\n\n"
                                                f"NOTE:\n{e['note']}"}]
            try:
                v = llm.complete_json("judge", msgs, SCHEMA, item=f"judge:{brief['case_no']}")
            except LLMError as err:
                v = {"error": str(err)}
            judged.append({"case_no": brief["case_no"], "segment_id": e["segment_id"],
                           "note": e["note"], **v})
    ok = [j for j in judged if "faithful" in j]
    summary = {
        "notes_judged": len(ok),
        "faithful_rate": sum(j["faithful"] for j in ok) / len(ok) if ok else None,
        "mean_usefulness": sum(j["usefulness"] for j in ok) / len(ok) if ok else None,
    }
    (out_dir / "judge.json").write_text(json.dumps({"summary": summary, "items": judged},
                                                   ensure_ascii=False, indent=2),
                                        encoding="utf-8")
    return {"summary": summary, "spot_check_sample": judged[:20]}
