"""Evaluation harness (§6.4).

    python eval/harness.py                  # all cases, replay mode (deterministic, offline)
    python eval/harness.py --live           # call the configured model, refresh the cache
    python eval/harness.py --case <id>      # one case
    python eval/harness.py --judge          # also run the LLM-as-judge on notes

Every case with labels runs twice: as described and titles-only (rule 4, §2.3). Output goes
to eval/runs/<timestamp>/ (results.json, report.md, and the pipeline's raw run logs).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

import typer
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from briefer import paths  # noqa: E402
from briefer.agenda import AgendaError, load  # noqa: E402
from briefer.fetch import FetchError, resolve_local  # noqa: E402
from briefer.pipeline import run as run_pipeline  # noqa: E402
from briefer.pipeline import slug  # noqa: E402
from eval.metrics import aggregate, score_item  # noqa: E402

app = typer.Typer(add_completion=False)
CASES = ROOT / "tests" / "cases"


def _fmt(x) -> str:
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.2f}"
    if isinstance(x, list) and len(x) == 2:
        return f"{x[0]}/{x[1]}"
    return str(x)


def missing_sources(agenda) -> list[str]:
    """Local attachments an open, in-scope item needs but this checkout lacks (e.g. the
    copyrighted test PDF on a fresh clone); the case is then reported as not run."""
    missing = set()
    for item in agenda.items:
        if item.closed or not item.in_scope:
            continue
        for att in item.attachments:
            if att.url.startswith("local:"):
                try:
                    resolve_local(att.url)
                except FetchError:
                    missing.add(att.url.removeprefix("local:"))
    return sorted(missing)


def candidate_recall(summary: dict, labels: dict) -> dict:
    """Diagnostic: recall if S8 had selected every S7 candidate (the retrieval ceiling)."""
    from briefer.models import ParsedDoc

    segs = {}
    for d in summary["documents"].values():
        sha = Path(d["path"]).stem
        for f in (paths.DERIVED / sha).glob("parsed_v*.json"):
            pd = ParsedDoc.model_validate_json(f.read_text(encoding="utf-8"))
            segs.update({s.id: (s, d["url"]) for s in pd.segments})
    cands: dict[str, list[str]] = {}
    with open(Path(summary["out_dir"]) / "run_log.jsonl", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["stage"] == "S7" and r["event"] == "candidates":
                cands[r["case_no"]] = [c["id"] for c in r["candidates"]]
    found = total = 0
    for case_no, ids in cands.items():
        gold = labels["items"].get(case_no, {})
        if gold.get("expect") != "passages":
            continue
        fake = {"case_no": case_no, "status": "awaiting_review", "llm_calls": 0, "extracts": [
            {"segment_id": i, "text": segs[i][0].text, "physical_page": segs[i][0].page,
             "source_url": f"{segs[i][1]}#page={segs[i][0].page}", "found_via": "search"}
            for i in ids if i in segs]}
        r = score_item(fake, gold)
        found += r["n_found"]
        total += r["n_gold"]
    return {"found": found, "gold": total, "recall": found / total if total else None}


def _expected_failures() -> list[dict]:
    """Cases whose agenda must be rejected by S0 (rejected input)."""
    out = []
    for f in sorted((CASES / "rejected_input").glob("*.yaml")):
        try:
            load(f)
            out.append({"case": f.name, "rejected": False})
        except AgendaError as e:
            out.append({"case": f.name, "rejected": True, "error": str(e).splitlines()[-1]})
    return out


@app.command()
def main(live: bool = False, case: str | None = None, judge: bool = False,
         lang: str = "nb") -> None:
    os.environ["BRIEFER_LLM_MODE"] = "live" if live else os.environ.get(
        "BRIEFER_EVAL_MODE", "replay")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = ROOT / "eval" / "runs" / stamp
    out.mkdir(parents=True)
    results = {"timestamp": stamp, "llm_mode": os.environ["BRIEFER_LLM_MODE"],
               "llm_config": paths.config("llm")["stages"], "cases": {}}

    agendas = sorted(CASES.glob("*/agenda.yaml"))
    if case:
        agendas = [a for a in agendas if a.parent.name == case]
    for agenda_path in agendas:
        agenda = load(agenda_path)
        meeting = agenda.meeting
        labels_file = ROOT / "labels" / f"{meeting.id}.yaml"
        if not labels_file.exists():
            # label before output (labelling guideline): an unlabelled case is not run
            typer.echo(f"== {agenda_path.parent.name}: no labels yet, not run")
            results.setdefault("unlabelled", []).append(agenda_path.parent.name)
            continue
        missing = missing_sources(agenda)
        if missing:
            typer.echo(f"== {agenda_path.parent.name}: source document missing "
                       f"({', '.join(missing)}), not run")
            results.setdefault("missing_sources", {})[agenda_path.parent.name] = missing
            continue
        labels = yaml.safe_load(labels_file.read_text(encoding="utf-8"))
        case_res = {}
        for style in ("described", "titles_only"):
            typer.echo(f"== {agenda_path.parent.name} [{style}]")
            summary = run_pipeline(agenda_path, lang, style, run_id=f"eval-{stamp}",
                                   out_root=out / "raw")
            rows = []
            for case_no, status in summary["statuses"].items():
                brief = json.loads((Path(summary["out_dir"]) / f"{slug(case_no)}.json"
                                    ).read_text(encoding="utf-8"))
                gold = labels["items"].get(case_no)
                if gold is None:
                    rows.append({"case_no": case_no, "expect": "unlabelled", "status": status,
                                 "n_selected": len(brief["extracts"]), "n_gold": 0,
                                 "correct": None,
                                 "verification": brief["verification"]["checks"]})
                    continue
                r = score_item(brief, gold)
                r["verification"] = brief["verification"]["checks"]
                r["removed"] = brief["verification"].get("removed", [])
                r["llm_calls"] = brief.get("llm_calls", 0)
                rows.append(r)
            if judge:
                from eval.judge import judge_run
                case_res.setdefault("judge", {})[style] = judge_run(Path(summary["out_dir"]))
            agg = aggregate([r for r in rows if r["expect"] != "unlabelled"])
            agg["candidate_recall"] = candidate_recall(summary, labels)["recall"]
            case_res[style] = {"summary": summary, "items": rows, "aggregate": agg}
        results["cases"][agenda_path.parent.name] = case_res
    results["rejected_input"] = _expected_failures()

    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False,
                                                 default=str), encoding="utf-8")
    (out / "report.md").write_text(report(results), encoding="utf-8")
    typer.echo(f"\nReport: {out / 'report.md'}")
    typer.echo(report_table(results))


def report_table(results: dict) -> str:
    lines = ["| case | style | recall (micro) | recall (macro) | precision (micro) | F1 | "
             "candidate recall (S7 ceiling) | xref recall | skips | rejects | V1–V5 removed | "
             "LLM calls | tokens | s |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, c in results["cases"].items():
        for style in ("described", "titles_only"):
            if style not in c:
                continue
            a, s = c[style]["aggregate"], c[style]["summary"]
            lines.append(
                f"| {name} | {style} | {_fmt(a['recall_micro'])} | {_fmt(a['recall_macro'])} | "
                f"{_fmt(a['precision_micro'])} | {_fmt(a['f1_micro'])} | "
                f"{_fmt(a.get('candidate_recall'))} | "
                f"{_fmt(a['recall_cross_reference_gold'])} | {_fmt(a['skip_correct'])} | "
                f"{_fmt(a['reject_correct'])} | "
                f"{s['extracts_failed']}/{s['extracts_checked']} | {s['llm_calls']} | "
                f"{s['tokens']} | {s['seconds']} |")
    return "\n".join(lines)


def report(results: dict) -> str:
    md = [f"# Evaluation report {results['timestamp']}", "",
          f"LLM mode: `{results['llm_mode']}` · models: " + ", ".join(
              f"{k}={v['model']}" for k, v in results["llm_config"].items()), "",
          "## Quantitative", "", report_table(results), ""]
    for name, c in results["cases"].items():
        for style in ("described", "titles_only"):
            if style not in c:
                continue
            md += [f"## {name} — {style}", "",
                   "| item | expected | status | gold | found | selected | recall | precision |",
                   "|---|---|---|---|---|---|---|---|"]
            for r in c[style]["items"]:
                md.append(f"| {r['case_no']} | {r['expect']} | {r['status']} | {r['n_gold']} | "
                          f"{r.get('n_found', '–')} | {r['n_selected']} | "
                          f"{_fmt(r.get('recall'))} | {_fmt(r.get('precision'))} |")
            if topics := c[style]["aggregate"].get("found_by_topic"):
                md += ["", "### Recall by subtopic", "", "| subtopic | found / gold |",
                       "|---|---|"]
                md += [f"| {t} | {f}/{n} |" for t, (f, n) in sorted(topics.items())]
            md += ["", "### Qualitative: misses and false positives", ""]
            for r in c[style]["items"]:
                if r.get("missed") or r.get("false_positives") or r.get("removed") or \
                        r.get("correct") is False:
                    md.append(f"**{r['case_no']}** ({r['status']}, expected {r['expect']})")
                    for m in r.get("missed", []):
                        tags = f" [{', '.join(m['topics'])}]" if m.get("topics") else ""
                        md.append(f"- missed p{m['page']}{tags}: “{m['quote']}…”")
                    for fp in r.get("false_positives", []):
                        if isinstance(fp, dict):
                            md.append(f"- extra p{fp['page']}: “{fp['text']}…”")
                        else:
                            md.append(f"- extra {fp}")
                    for rm in r.get("removed", []):
                        md.append(f"- removed by verification: {rm['segment_id']}: "
                                  f"{'; '.join(rm['failures'])}")
                    md.append("")
            if "judge" in c and style in c["judge"]:
                j = c["judge"][style]
                md += ["### LLM-as-judge (notes)", "", f"{json.dumps(j['summary'])}", ""]
    if results.get("unlabelled"):
        md += ["Not run (no labels yet): " + ", ".join(results["unlabelled"]), ""]
    for name, files in results.get("missing_sources", {}).items():
        md += [f"Not run (source document missing): {name} ({', '.join(files)})", ""]
    md += ["## Rejected input (S0)", ""]
    for r in results.get("rejected_input", []):
        md.append(f"- {r['case']}: {'rejected ✓' if r['rejected'] else 'ACCEPTED ✗'} "
                  f"{r.get('error', '')}")
    md += ["", "Raw pipeline logs: `raw/` in this directory (run_log.jsonl per run)."]
    return "\n".join(md)


if __name__ == "__main__":
    app()
