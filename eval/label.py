"""Labelling helper (T29). Writes labels/<meeting_id>.yaml; refuses quotes that fail V1.

    python eval/label.py find  <agenda.yaml> "<phrase>" [--context 200]
    python eval/label.py add   <agenda.yaml> <case_no> <page> "<quote>" [--via cross_reference]
    python eval/label.py expect <agenda.yaml> <case_no> passages|nothing_found|skipped
    python eval/label.py check <agenda.yaml>
    python eval/label.py agree <labels_a.yaml> <labels_b.yaml> <agenda.yaml>
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz
import typer
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from briefer.agenda import load  # noqa: E402
from briefer.fetch import fetch  # noqa: E402
from briefer.parse import page_text  # noqa: E402
from briefer.text import normalize  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)
LABELS = ROOT / "labels"


def _labels_path(meeting_id: str) -> Path:
    return LABELS / f"{meeting_id}.yaml"


def read_labels(meeting_id: str) -> dict:
    p = _labels_path(meeting_id)
    if p.exists():
        return yaml.safe_load(p.read_text(encoding="utf-8"))
    return {"meeting_id": meeting_id, "labeller": "", "reviewed_by": None, "items": {}}


def _write(meeting_id: str, data: dict) -> None:
    LABELS.mkdir(exist_ok=True)
    _labels_path(meeting_id).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8")


def _docs(agenda_path: Path) -> dict[str, fitz.Document]:
    """Readable attachments only: refused URLs and corrupt PDFs cannot hold gold passages."""
    agenda = load(agenda_path)
    out = {}
    for u in {a.url for i in agenda.items for a in i.attachments}:
        try:
            d = fitz.open(fetch(u).path)
            if d.page_count:
                out[u] = d
        except Exception as e:  # noqa: BLE001
            typer.echo(f"(skipping unreadable attachment {u}: {e})", err=True)
    return out


@app.command()
def find(agenda: Path, phrase: str, context: int = 160, limit: int = 15) -> None:
    """Search all attachments for a phrase (case-insensitive) and print page + context."""
    needle = normalize(phrase).lower()
    shown = 0
    for url, doc in _docs(agenda).items():
        for i in range(doc.page_count):
            t = page_text(doc[i])
            pos = t.lower().find(needle)
            while pos >= 0 and shown < limit:
                a, b = max(0, pos - context), pos + len(needle) + context
                typer.echo(f"--- {url} page {i + 1}\n…{t[a:b]}…\n")
                shown += 1
                pos = t.lower().find(needle, pos + 1)


@app.command()
def add(agenda: Path, case_no: str, physical_page: int, quote: str,
        via: str = "search", section: str = "") -> None:
    """Add a gold passage. The quote must be verbatim on the page after normalisation."""
    meeting = load(agenda).meeting
    q = normalize(quote)
    docs = _docs(agenda)
    hits = [u for u, d in docs.items()
            if physical_page <= d.page_count and q in page_text(d[physical_page - 1])]
    if not hits:
        typer.echo(f"REFUSED: quote not found verbatim on page {physical_page}", err=True)
        raise typer.Exit(1)
    data = read_labels(meeting.id)
    item = data["items"].setdefault(case_no, {"expect": "passages", "passages": []})
    item.setdefault("passages", []).append(
        {"document": hits[0], "physical_page": physical_page, "section": section,
         "via": via, "quote": q})
    _write(meeting.id, data)
    typer.echo(f"added to {case_no}: p{physical_page} {q[:70]}…")


@app.command()
def expect(agenda: Path, case_no: str, outcome: str) -> None:
    if outcome not in ("passages", "nothing_found", "skipped"):
        raise typer.BadParameter("passages | nothing_found | skipped")
    meeting = load(agenda).meeting
    data = read_labels(meeting.id)
    data["items"].setdefault(case_no, {"passages": []})["expect"] = outcome
    _write(meeting.id, data)


@app.command()
def check(agenda: Path) -> None:
    """Re-check every gold quote against its page (V1 for labels)."""
    meeting = load(agenda).meeting
    data = read_labels(meeting.id)
    docs = _docs(agenda)
    bad = 0
    for case, item in data["items"].items():
        for p in item.get("passages", []):
            if p["quote"] not in page_text(docs[p["document"]][p["physical_page"] - 1]):
                bad += 1
                typer.echo(f"FAIL {case} p{p['physical_page']}: {p['quote'][:60]}")
    n = sum(len(i.get("passages", [])) for i in data["items"].values())
    typer.echo(f"{n - bad}/{n} gold passages verbatim on their page")
    raise typer.Exit(1 if bad else 0)


@app.command()
def agree(labels_a: Path, labels_b: Path, agenda: Path) -> None:
    """Inter-annotator agreement: segment-level F1 and Cohen's kappa."""
    from eval.metrics import agreement

    a = yaml.safe_load(labels_a.read_text(encoding="utf-8"))
    b = yaml.safe_load(labels_b.read_text(encoding="utf-8"))
    typer.echo(agreement(a, b, agenda))


if __name__ == "__main__":
    app()
