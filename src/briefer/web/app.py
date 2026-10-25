"""S11 — Review and approve (web UI). Local, single organiser, no accounts (§7).

Only approved briefs can be exported. Extracts are always shown in the source language and
never altered; the organiser can remove and reorder them, add a note, choose the brief
language (UI strings and disclaimer), and approve or reject.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from pathlib import Path

import fitz
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from .. import assemble, paths
from . import store

app = FastAPI(title="Agenda Brief Builder — review")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_SAFE = re.compile(r"^[A-Za-z0-9_.\-]+$")

UI = {
    "nb": {"meetings": "Møter", "items": "Saker", "status": "Status", "review": "Gjennomgå",
           "remove": "Fjern", "restore": "Gjenopprett", "up": "Opp", "down": "Ned",
           "note": "Merknad fra møtesekretariatet", "save": "Lagre", "approve": "Godkjenn",
           "reject": "Avvis", "export": "Eksporter", "language": "Språk i brief",
           "removed": "Fjernet", "source": "Kilde", "audit": "Logg",
           "only_approved": "Kun godkjente briefer kan eksporteres.",
           "extracts": "utdrag", "page": "side", "run": "Kjøring", "style": "Stil"},
    "nn": {"meetings": "Møte", "items": "Saker", "status": "Status", "review": "Gå gjennom",
           "remove": "Fjern", "restore": "Gjenopprett", "up": "Opp", "down": "Ned",
           "note": "Merknad frå møtesekretariatet", "save": "Lagre", "approve": "Godkjenn",
           "reject": "Avvis", "export": "Eksporter", "language": "Språk i brief",
           "removed": "Fjerna", "source": "Kjelde", "audit": "Logg",
           "only_approved": "Berre godkjende brief kan eksporterast.",
           "extracts": "utdrag", "page": "side", "run": "Køyring", "style": "Stil"},
    "en": {"meetings": "Meetings", "items": "Items", "status": "Status", "review": "Review",
           "remove": "Remove", "restore": "Restore", "up": "Up", "down": "Down",
           "note": "Organiser's note", "save": "Save", "approve": "Approve",
           "reject": "Reject", "export": "Export", "language": "Brief language",
           "removed": "Removed", "source": "Source", "audit": "Log",
           "only_approved": "Only approved briefs can be exported.",
           "extracts": "extracts", "page": "page", "run": "Run", "style": "Style"},
}


def _lang(request: Request) -> str:
    lang = request.cookies.get("ui_lang") or os.environ.get("BRIEFER_UI_LANG", "nb")
    return lang if lang in UI else "nb"


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
    return templates.TemplateResponse(request, "login.html", {"t": UI[_lang(request)]})


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
    for f in sorted(paths.RUNS.glob("*/*/*/run.json"), reverse=True):
        s = json.loads(f.read_text(encoding="utf-8"))
        rel = f.parent.relative_to(paths.RUNS).parts
        runs.append({"path": "/".join(rel), "summary": s})
    return templates.TemplateResponse(request, "index.html", {"t": UI[_lang(request)],
                                                              "runs": runs[:100]})


@app.get("/m/{run_id}/{meeting}/{style}", response_class=HTMLResponse)
def meeting(run_id: str, meeting: str, style: str, request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    summary = json.loads((d / "run.json").read_text(encoding="utf-8"))
    items = []
    for case_no in summary["statuses"]:
        case = re.sub(r"[^A-Za-z0-9]+", "_", case_no).strip("_")
        brief, _ = _brief(d, case)
        state = store.get_state(_key(run_id, meeting, style, case), brief)
        items.append({"case": case, "brief": brief, "state": state,
                      "n": len(set(state["order"]) - set(state["removed"]))})
    return templates.TemplateResponse(request, "meeting.html", {
        "t": UI[_lang(request)], "summary": summary, "items": items,
        "base": f"{run_id}/{meeting}/{style}"})


@app.get("/i/{run_id}/{meeting}/{style}/{case}", response_class=HTMLResponse)
def item(run_id: str, meeting: str, style: str, case: str, request: Request):
    _check_auth(request)
    d = _run_dir(run_id, meeting, style)
    brief, _ = _brief(d, case)
    key = _key(run_id, meeting, style, case)
    state = store.get_state(key, brief)
    by_id = {e["segment_id"]: e for e in brief["extracts"]}
    ordered = [by_id[i] for i in state["order"] if i in by_id]
    return templates.TemplateResponse(request, "item.html", {
        "t": UI[_lang(request)], "brief": brief, "state": state, "extracts": ordered,
        "base": f"{run_id}/{meeting}/{style}", "case": case, "audit": store.audit(key),
        "note_label": assemble.NOTE_LABEL[state["language"]]})


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
