"""Command line: `briefer run`, `briefer watch`, `briefer ui`, `briefer purge`."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import stat
import time
from pathlib import Path

import typer

from . import paths

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _load_dotenv() -> None:
    env = paths.ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


@app.command()
def run(agenda: Path, lang: str = typer.Option("nb", help="brief language: nb | nn | en"),
        style: str = typer.Option("described", help="described | titles_only"),
        verbose: bool = False) -> None:
    """Run S0–S10 for one agenda file. Briefs stop at 'awaiting review'."""
    from .agenda import AgendaError
    from .pipeline import run as run_pipeline
    from .safety import KillSwitch

    _load_dotenv()
    _setup_logging(verbose)
    if lang not in ("nb", "nn", "en"):
        raise typer.BadParameter("lang must be nb, nn or en")
    try:
        summary = run_pipeline(agenda, lang, style)
    except AgendaError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from e
    except KillSwitch as e:
        typer.echo(f"HALTED: {e}", err=True)
        raise typer.Exit(3) from e
    typer.echo(json.dumps({k: summary[k] for k in (
        "run_id", "statuses", "halted", "extracts_checked", "extracts_failed", "llm_calls",
        "tokens", "seconds", "out_dir")}, indent=2, ensure_ascii=False))


@app.command()
def watch(interval: int = typer.Option(300, help="seconds between inbox scans"),
          once: bool = typer.Option(False, help="scan once and exit (for cron / task scheduler)"),
          lang: str = "nb") -> None:
    """Process every new agenda.yaml dropped into inbox/ without a person."""
    from .pipeline import run as run_pipeline

    _load_dotenv()
    _setup_logging(True)
    seen_file = paths.RUNS / ".processed.json"
    while True:
        seen = json.loads(seen_file.read_text()) if seen_file.exists() else {}
        for f in sorted(paths.INBOX.glob("*.yaml")):
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            if seen.get(f.name) == h:
                continue
            try:
                s = run_pipeline(f, lang, "described")
                logging.info("inbox %s -> %s %s", f.name, s["run_id"], s["statuses"])
            except Exception as e:  # noqa: BLE001 — one bad file must not stop the watcher
                logging.error("inbox %s failed: %s", f.name, e)
            seen[f.name] = h
            seen_file.parent.mkdir(parents=True, exist_ok=True)
            seen_file.write_text(json.dumps(seen, indent=2))
        if once:
            return
        time.sleep(interval)


@app.command()
def ui(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the local review UI (S11)."""
    import uvicorn

    _load_dotenv()
    uvicorn.run("briefer.web.app:app", host=host, port=port)


@app.command()
def purge(older_than_days: int | None = typer.Option(
        None, help="only delete cached data older than this; default deletes all")) -> None:
    """Delete cached PDFs and derived data (§9 retention)."""
    cutoff = time.time() - older_than_days * 86400 if older_than_days is not None else None
    removed = 0
    for base in (paths.RAW, paths.DERIVED, paths.LLM_CACHE):
        if not base.exists():
            continue
        for p in list(base.iterdir()):
            if cutoff is None or p.stat().st_mtime < cutoff:
                if p.is_dir():
                    shutil.rmtree(p, onerror=lambda f, x, _: (os.chmod(x, stat.S_IWRITE), f(x)))
                else:
                    os.chmod(p, stat.S_IWRITE)
                    p.unlink()
                removed += 1
    typer.echo(f"purged {removed} entries")


if __name__ == "__main__":
    app()
