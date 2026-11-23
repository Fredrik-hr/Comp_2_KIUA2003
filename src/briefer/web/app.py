"""S11 — Review and approve (web UI). Local, single organiser, no accounts (§7).

Only approved briefs can be exported. Extracts are always shown in the source language and
never altered; the organiser can remove and reorder them, add a note, choose the brief
language (UI strings and disclaimer), and approve or reject.

The organiser can also upload an agenda. It is validated in memory, saved to
inbox/pending/ under a normalised name, previewed, and only moved to inbox/ and run when
the organiser presses Start.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import os
import re
from pathlib import Path
from typing import Annotated

import fitz
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import assemble, paths, pipeline
from ..agenda import Agenda, AgendaError, gate, parse
from . import store
from .i18n import LANGS, UI

log = logging.getLogger(__name__)
app = FastAPI(title="Agenda Brief Builder — review")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_UPLOAD = re.compile(r"^upload_\d{8}-\d{6}_[A-Za-z0-9_]+\.yaml$")
MAX_UPLOAD = 200 * 1024
EXAMPLE_AGENDA = Path("tests") / "cases" / "algorithms_synthetic" / "agenda.yaml"


def _lang(request: Request) -> str:
    lang = request.cookies.get("ui_lang") or os.environ.get("BRIEFER_UI_LANG", "nb")
    return lang if lang in UI else "nb"


def _page(request: Request, template: str, status_code: int = 200, **ctx) -> HTMLResponse:
    lang = _lang(request)
    return templates.TemplateResponse(request, template, {"t": UI[lang], "lang": lang,
                                                      "langs": LANGS, "section": "meetings",
                                                      **ctx},
                                      status_code=status_code)


def _check_auth(request: Request) -> None:
    secret = os.environ.get("BRIEFER_UI_PASSPHRASE", "")
    if not secret:
        return
    token = hashlib.sha256(secret.encode()).hexdigest()
    if not hmac.compare_digest(request.cookies.get("auth", ""), token):
        raise HTTPException(status_code=303, headers={"Location": "/login"})


def _run_dir(run_id: str, meeting: str, style: str) -> Path:
    for part in (run_id, meeting, style):
        if not _SAFE.match(part):
            raise HTTPException(400, "bad path")
    d = (paths.RUNS / run_id / meeting / style).resolve()
    if paths.RUNS.resolve() not in d.parents or not (d / "run.json").exists():
        raise HTTPException(404, "run not found")
    return d


def _brief(d: Path, case: str) -> tuple[dict, Path]:
    if not _SAFE.match(case):
        raise HTTPException(400, "bad case")
    p = d / f"{case}.json"
    if not p.exists():
        raise HTTPException(404, "brief not found")
    return json.loads(p.read_text(encoding="utf-8")), p


def _key(run_id: str, meeting: str, style: str, case: str) -> str:
    return f"{run_id}/{meeting}/{style}/{case}"


def _case(case_no: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", case_no).strip("_")


def _items(d: Path, summary: dict, run_id: str, meeting: str, style: str) -> list[dict]:
    """Every brief in a run with the organiser's current review state."""
    items = []
    for case_no in summary["statuses"]:
        case = _case(case_no)
        brief, _ = _brief(d, case)
        state = store.get_state(_key(run_id, meeting, style, case), brief)
        items.append({"case": case, "brief": brief, "state": state,
                      "n": len(set(state["order"]) - set(state["removed"]))})
    return items


def _agenda(summary: dict) -> tuple[Agenda | None, str | None]:
    """The agenda file the run recorded, read-only. (None, None) if it is gone or invalid."""
    p = Path(str(summary.get("agenda", "")).replace("\\", "/"))
    if not p.is_absolute():
        p = paths.ROOT / p
    try:
        text = p.read_text(encoding="utf-8")
        return parse(text, p.name), text
    except (OSError, AgendaError):
        return None, None


def _queries(queries: list[dict]) -> list[dict]:
    """Merge identical search phrases across languages: nb + nn → "nb·nn"."""
    merged: dict[str, list[str]] = {}
    for q in queries:
        merged.setdefault(q["text"], []).append(q["lang"])
    return [{"lang": "·".join(langs), "text": text} for text, langs in merged.items()]


def _interpretations(d: Path) -> dict[str, dict]:
    """S6 topic and queries per case, from the run log."""
    out: dict[str, dict] = {}
    log_file = d / "run_log.jsonl"
    if not log_file.exists():
        return out
    for line in log_file.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("stage") == "S6" and rec.get("event") == "understood":
            out[rec["case_no"]] = {"topic": rec.get("topic", ""),
                                   "queries": _queries(rec.get("queries", []))}
    return out


def _skip_kind(reason: str | None) -> str | None:
    if not reason:
        return None
    if reason.startswith("closed"):
        return "closed"
    if reason.startswith("procedural"):
        return "procedural"
    return "scope"


def reviewed(brief: dict, state: dict) -> dict:
    """The brief as the organiser left it: removed extracts dropped, order applied."""
    by_id = {e["segment_id"]: e for e in brief["extracts"]}
    extracts = [by_id[i] for i in state["order"] if i in by_id and i not in state["removed"]]
    lang = state["language"]
    out = {**brief, "extracts": extracts, "status": state["status"], "brief_language": lang,
           "disclaimer": assemble.DISCLAIMER[lang]}
    if state.get("organiser_note"):
        out["organiser_note"] = state["organiser_note"]
    return out


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return _page(request, "login.html")


@app.post("/login")
def login(passphrase: str = Form(...)):
    secret = os.environ.get("BRIEFER_UI_PASSPHRASE", "")
    if not secret or not hmac.compare_digest(passphrase, secret):
        return RedirectResponse("/login", status_code=303)
    r = RedirectResponse("/", status_code=303)
    r.set_cookie("auth", hashlib.sha256(secret.encode()).hexdigest(), httponly=True,
                 samesite="strict")
    return r


@app.get("/lang/{lang}")
def set_lang(lang: str, request: Request):
    r = RedirectResponse(request.headers.get("referer", "/"), status_code=303)
    if lang in UI:
        r.set_cookie("ui_lang", lang, samesite="strict")
    return r


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    _check_auth(request)
    runs = []
    for f in sorted(paths.RUNS.glob("*/*/*/run.json"), reverse=True)[:100]:
        s = json.loads(f.read_text(encoding="utf-8"))
        run_id, meeting, style = f.parent.relative_to(paths.RUNS).parts
        try:
            items = _items(f.parent, s, run_id, meeting, style)
        except HTTPException:
            items = []
        statuses = [i["state"]["status"] for i in items]
        docs = s.get("documents", {}).values()
        agenda, _ = _agenda(s)
        runs.append({"path": f"{run_id}/{meeting}/{style}", "summary": s, "n": len(items),
                     "meeting": agenda.meeting if agenda else None,
                     "approved": statuses.count("approved"),
                     "awaiting": statuses.count("awaiting_review"),
                     "extracts": sum(i["n"] for i in items), "docs": len(docs),
                     "pages": sum(doc.get("pages") or 0 for doc in docs)})
    return _page(request, "index.html", runs=runs)


@app.get("/how", response_class=HTMLResponse)
def how(request: Request):
    _check_auth(request)
    return _page(request, "how.html", section="how")


@app.get("/m/{run_id}/{meeting}/{style}", response_class=HTMLResponse)
def meeting(run_id: str, meeting: str, style: str, request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    summary = json.loads((d / "run.json").read_text(encoding="utf-8"))
    items = _items(d, summary, run_id, meeting, style)
    agenda, raw = _agenda(summary)
    by_case = {i.case_no: i for i in agenda.items} if agenda else {}
    interp = _interpretations(d)
    for i in items:
        i["agenda"] = by_case.get(i["brief"]["case_no"])
        i["interp"] = interp.get(i["brief"]["case_no"])
    statuses = [i["state"]["status"] for i in items]
    checked = summary.get("extracts_checked") or 0
    return _page(request, "meeting.html", summary=summary, items=items, agenda=agenda, raw=raw,
                 agenda_name=Path(str(summary.get("agenda", "")).replace("\\", "/")).name,
                 base=f"{run_id}/{meeting}/{style}",
                 stats={"approved": statuses.count("approved"),
                        "awaiting": statuses.count("awaiting_review"),
                        "passed": checked - (summary.get("extracts_failed") or 0),
                        "checked": checked},
                 first=next((i["case"] for i in items if i["state"]["status"]
                             == "awaiting_review"), items[0]["case"] if items else None))


@app.get("/i/{run_id}/{meeting}/{style}/{case}", response_class=HTMLResponse)
def item(run_id: str, meeting: str, style: str, case: str, request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    brief, _ = _brief(d, case)
    key = _key(run_id, meeting, style, case)
    state = store.get_state(key, brief)
    by_id = {e["segment_id"]: e for e in brief["extracts"]}
    ordered = [by_id[i] for i in state["order"] if i in by_id]
    summary = json.loads((d / "run.json").read_text(encoding="utf-8"))
    return _page(request, "item.html", brief=brief, state=state, extracts=ordered,
                 base=f"{run_id}/{meeting}/{style}", case=case, audit=store.audit(key),
                 note_label=assemble.NOTE_LABEL[state["language"]],
                 siblings=_items(d, summary, run_id, meeting, style),
                 interp=_interpretations(d).get(brief["case_no"]),
                 kept=len([s for s in state["order"] if s not in state["removed"]]))


@app.post("/i/{run_id}/{meeting}/{style}/{case}/action")
def action(run_id: str, meeting: str, style: str, case: str, request: Request,
           op: str = Form(...), segment_id: str = Form(""), note: str = Form(""),
           language: str = Form("")):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    brief, _ = _brief(d, case)
    key = _key(run_id, meeting, style, case)
    state = store.get_state(key, brief)
    if state["status"] in ("skipped", "halted") and op in ("approve",):
        raise HTTPException(400, "this item cannot be approved")
    if op == "remove" and segment_id in state["order"]:
        state["removed"] = sorted(set(state["removed"]) | {segment_id})
    elif op == "restore":
        state["removed"] = [s for s in state["removed"] if s != segment_id]
    elif op in ("up", "down") and segment_id in state["order"]:
        o = state["order"]
        i = o.index(segment_id)
        j = i - 1 if op == "up" else i + 1
        if 0 <= j < len(o):
            o[i], o[j] = o[j], o[i]
    elif op == "note":
        state["organiser_note"] = note.strip()[:2000]
    elif op == "language" and language in assemble.DISCLAIMER:
        state["language"] = language
    elif op == "approve":
        state["status"] = "approved"
    elif op == "reject":
        state["status"] = "rejected"
    else:
        raise HTTPException(400, "unknown action")
    # Any edit after approval sends the brief back for review.
    if op not in ("approve", "reject") and state["status"] == "approved":
        state["status"] = "awaiting_review"
    store.save_state(key, state, op, segment_id or language or note[:80])
    return RedirectResponse(f"/i/{run_id}/{meeting}/{style}/{case}", status_code=303)


@app.get("/page/{run_id}/{meeting}/{style}/{doc_id}/{page}.png")
def page_png(run_id: str, meeting: str, style: str, doc_id: str, page: int,
             request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    docs = json.loads((d / "run.json").read_text(encoding="utf-8"))["documents"]
    if doc_id not in docs:
        raise HTTPException(404, "document not in this run")
    pdf = fitz.open(docs[doc_id]["path"])
    if not 1 <= page <= pdf.page_count:
        raise HTTPException(404, "page out of range")
    png = pdf[page - 1].get_pixmap(dpi=90).tobytes("png")
    return Response(png, media_type="image/png")


@app.get("/export/{run_id}/{meeting}/{style}/{case}.{fmt}")
def export(run_id: str, meeting: str, style: str, case: str, fmt: str, request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    brief, _ = _brief(d, case)
    key = _key(run_id, meeting, style, case)
    state = store.get_state(key, brief)
    if state["status"] != "approved":
        raise HTTPException(403, "only approved briefs can be exported")
    final = reviewed(brief, state)
    store.save_state(key, state, "export", fmt)
    if fmt == "html":
        return HTMLResponse(assemble.to_html(final))
    if fmt == "md":
        return Response(assemble.to_markdown(final), media_type="text/markdown; charset=utf-8")
    if fmt == "json":
        return Response(json.dumps(final, ensure_ascii=False, indent=2),
                        media_type="application/json")
    raise HTTPException(400, "format must be html, md or json")


# --- Upload ---------------------------------------------------------------------------


@app.get("/example-agenda.yaml")
def example_agenda(request: Request):
    _check_auth(request)
    return FileResponse(paths.ROOT / EXAMPLE_AGENDA, media_type="text/yaml; charset=utf-8",
                        filename="agenda.yaml")


@app.post("/upload", response_class=HTMLResponse)
async def upload(request: Request, file: Annotated[UploadFile | None, File()] = None):
    _check_auth(request)
    t = UI[_lang(request)]
    errors: list[str] = []
    agenda = None
    if file is None or not file.filename:
        errors = [t["err_empty"]]
    elif Path(file.filename).suffix.lower() not in (".yaml", ".yml"):
        errors = [t["err_ext"]]
    else:
        data = await file.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            errors = [t["err_size"]]
        else:
            try:
                agenda = parse(data.decode("utf-8"), "agenda.yaml")
            except UnicodeDecodeError:
                errors = [t["err_encoding"]]
            except AgendaError as e:
                # Validation errors: one field per line after the header. YAML syntax
                # errors: keep the whole message.
                lines = str(e).splitlines()
                errors = ([ln.strip() for ln in lines[1:]] if "invalid agenda" in lines[0]
                          else [str(e)])
    if agenda is None:
        return _page(request, "upload.html", status_code=400, view="error", errors=errors)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"upload_{stamp}_{pipeline.slug(agenda.meeting.id) or 'agenda'}.yaml"
    paths.INBOX_PENDING.mkdir(parents=True, exist_ok=True)
    (paths.INBOX_PENDING / name).write_bytes(data)
    return RedirectResponse(f"/upload/{name}", status_code=303)


def _upload_name(name: str) -> str:
    if not _UPLOAD.match(name):
        raise HTTPException(400, "bad upload name")
    return name


@app.get("/upload/{name}", response_class=HTMLResponse)
def upload_preview(name: str, request: Request):
    _check_auth(request)
    name = _upload_name(name)
    pending, started = paths.INBOX_PENDING / name, paths.INBOX / name
    if pending.exists():
        agenda = parse(pending.read_text(encoding="utf-8"), name)
        rows = [{"item": g.item, "process": g.process, "skip": _skip_kind(g.skip_reason)}
                for g in (gate(i) for i in agenda.items)]
        urls = sorted({a.url for i in agenda.items for a in i.attachments})
        return _page(request, "upload.html", view="preview", name=name, agenda=agenda,
                     rows=rows, urls=urls, size=pending.stat().st_size,
                     n_process=sum(r["process"] for r in rows))
    if started.exists():
        agenda = parse(started.read_text(encoding="utf-8"), name)
        return _page(request, "upload.html", view="started", name=name, agenda=agenda,
                     n_process=sum(gate(i).process for i in agenda.items))
    return _page(request, "upload.html", status_code=404, view="error",
                 errors=[UI[_lang(request)]["not_found"]])


def _run_upload(path: Path) -> None:
    try:
        s = pipeline.run(path, "nb", "described")
        log.info("upload %s -> %s %s", path.name, s["run_id"], s["statuses"])
    except Exception:  # noqa: BLE001 — a failed run must not take down the UI
        log.exception("upload %s failed", path.name)


@app.post("/upload/{name}/start")
def upload_start(name: str, request: Request, background: BackgroundTasks):
    _check_auth(request)
    name = _upload_name(name)
    src, dst = paths.INBOX_PENDING / name, paths.INBOX / name
    if not src.exists():
        raise HTTPException(404, "upload not found or already started")
    if dst.exists():
        raise HTTPException(409, "already started")
    src.replace(dst)
    pipeline.mark_processed(dst)  # so `watch` does not run it a second time
    background.add_task(_run_upload, dst)
    return RedirectResponse(f"/upload/{name}", status_code=303)
