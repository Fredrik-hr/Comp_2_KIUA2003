"""Agenda import: turn an uploaded møteinnkalling (PDF or .docx) into a draft agenda.

Code only, no LLM. The converter reads the meeting header and the saksliste (case number
and title per item) and suggests an item type from the case-number prefix. It never
decides `closed` or `in_scope`: those have no defaults (§10.1), so a draft stays
incomplete until the organiser sets them, and `to_agenda` refuses it until then.
Titles that look like they contain a person's name are flagged and must be edited.
`description` and `recommendation` are left empty (the pipeline accepts None).
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import paths
from .agenda import Agenda, ItemType
from .privacy import NameRules, detect

SUFFIXES = (".pdf", ".docx")
MAX_PAGES = 15

CASE_RE = re.compile(r"^(PS|RS|OS|DS|FO)\s+(\d{1,4}/\d{2,4})\b\s*(.*)$")
TYPE_BY_PREFIX = {"PS": ItemType.case, "RS": ItemType.information,
                  "DS": ItemType.information, "OS": ItemType.question,
                  "FO": ItemType.question}
# A mark in the "UOFF (Lukket)" column, or an exemption reference in the title.
CLOSED_MARK = re.compile(r"^(?:x|lukket|u\.?\s*off\.?.*|offl\.?\s*§.*|unntatt.*)$", re.I)
CLOSED_HINT = re.compile(r"unntatt offentlighet|offl\.?\s*§|lukket møte", re.I)
# Lines that end a saksliste block: legend ("PS = Politisk sak"), page numbers, headings.
STOP = re.compile(r"^(?:[A-ZÆØÅ]{2,4}\s*=|\d{1,4}$|Saksframlegg$|Saksliste$)")
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
MUNI_RE = re.compile(r"\b([A-ZÆØÅ][\wæøåÆØÅ-]+ (?:fylkeskommune|kommune))\b")


class AgendaImportError(ValueError):
    """Raised when an uploaded file cannot be converted. The message is shown to the organiser."""


@dataclass
class DraftItem:
    case_no: str
    title: str
    type: str
    suggested_closed: bool = False
    closed: bool | None = None
    in_scope: bool | None = None
    name_flags: list[str] = field(default_factory=list)


@dataclass
class Draft:
    meeting_id: str = ""
    body: str = ""
    municipality: str = ""
    date: str = ""              # ISO yyyy-mm-dd, empty if not found
    written_standard: str = "nb"
    public_url: str = ""
    items: list[DraftItem] = field(default_factory=list)


# --- reading ----------------------------------------------------------------------------

def _clean(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace(" ", " ")).strip()


def extract_pages(path: Path, max_pages: int = MAX_PAGES) -> list[list[str]]:
    """Text lines per page. A .docx is one page; table rows are separated by a blank line."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        import fitz

        try:
            with fitz.open(path) as doc:
                return [[_clean(x) for x in doc[i].get_text().splitlines()]
                        for i in range(min(max_pages, doc.page_count))]
        except Exception as e:  # noqa: BLE001 — any parser error means "not a readable PDF"
            raise AgendaImportError(f"cannot read PDF: {e}") from e
    if suffix == ".docx":
        import docx

        try:
            d = docx.Document(str(path))
        except Exception as e:  # noqa: BLE001
            raise AgendaImportError(f"cannot read Word document: {e}") from e
        lines = [_clean(p.text) for p in d.paragraphs]
        for table in d.tables:
            for row in table.rows:
                seen: list[str] = []
                for cell in row.cells:          # merged cells repeat; keep each once
                    t = _clean(cell.text)
                    if t not in seen:
                        seen.append(t)
                lines += [x for c in seen for x in c.split("\n")] + [""]
        return [lines]
    raise AgendaImportError(f"unsupported file type {suffix!r}: upload .pdf or .docx")


# --- parsing ----------------------------------------------------------------------------

def _value_after(lines: list[str], label: str) -> str:
    """'Utvalg: X' on one line, or 'Utvalg:' with the value on the next non-empty line."""
    for i, line in enumerate(lines):
        m = re.match(rf"^{label}\s*:\s*(.*)$", line, re.I)
        if m:
            if m.group(1):
                return m.group(1)
            return next((x for x in lines[i + 1:i + 4] if x), "")
    return ""


def _items(lines: list[str]) -> list[DraftItem]:
    items: list[DraftItem] = []
    cur: DraftItem | None = None
    parts: list[str] = []

    def close() -> None:
        if cur is not None:
            cur.title = _clean(" ".join(parts))
            if CLOSED_HINT.search(cur.title):
                cur.suggested_closed = True
            items.append(cur)

    for line in lines:
        m = CASE_RE.match(line)
        if m:
            close()
            prefix, num, rest = m.groups()
            cur = DraftItem(case_no=f"{prefix} {num}", title="",
                            type=TYPE_BY_PREFIX[prefix].value)
            parts = [rest] if rest else []
            continue
        if cur is None:
            continue
        if not line or STOP.match(line):
            if parts:               # blank line after the title ends the item
                close()
                cur, parts = None, []
            continue
        if CLOSED_MARK.match(line):
            cur.suggested_closed = True
            continue
        parts.append(line)
    close()
    return [i for i in items if i.title]


def _slug(text: str) -> str:
    t = text.lower().translate(str.maketrans({"æ": "ae", "ø": "o", "å": "a"}))
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def parse(pages: list[list[str]]) -> Draft:
    """Meeting header and saksliste from the first pages. Items are taken from the first
    run of pages that list cases; a case number seen twice keeps its first title."""
    flat = [x for p in pages for x in p]
    draft = Draft()
    draft.body = _value_after(flat, "Utvalg") or _value_after(flat, "Møte i")
    d = DATE_RE.search(_value_after(flat, "Dato") or _value_after(flat, "Møtedato") or "")
    if d:
        try:
            draft.date = dt.date(int(d[3]), int(d[2]), int(d[1])).isoformat()
        except ValueError:
            pass
    munis = Counter(MUNI_RE.findall("\n".join(flat)))
    if munis:
        fylke = [m for m in munis if m.endswith("fylkeskommune")]
        draft.municipality = max(fylke or munis, key=lambda m: munis[m])
    if draft.body and draft.date:
        draft.meeting_id = f"{_slug(draft.body)}_{draft.date}"

    seen: set[str] = set()
    started = False
    for page in pages:
        found = _items(page)
        if started and not found:
            break
        started = started or bool(found)
        for it in found:
            if it.case_no not in seen:
                seen.add(it.case_no)
                draft.items.append(it)
    flag_names(draft)
    return draft


def flag_names(draft: Draft) -> None:
    """Flag titles that look like they hold a person's name or contact details."""
    rules = NameRules(paths.config("privacy")["name_rules"])
    for it in draft.items:
        flags = detect(it.title)
        words = [w.strip(",;:()«»\"") for w in it.title.split()]
        # Two capitalised non-place words in a row after the first word ("... fra Kari Hansen").
        if rules.is_name(it.title, None) or rules._has_name_run(words[1:]):
            flags.append("pii:name")
        it.name_flags = flags


def convert(path: Path) -> Draft:
    draft = parse(extract_pages(path))
    if not draft.items:
        raise AgendaImportError("no agenda items found (expected lines such as 'PS 12/26 Title')")
    return draft


# --- output -----------------------------------------------------------------------------

def attachment_for(draft: Draft, pdf: Path | None) -> dict | None:
    """The case-paper PDF as an agenda attachment (`local:` path relative to the project
    root when possible, so fetch.resolve_local finds it)."""
    if pdf is None:
        return None
    try:
        rel = Path(pdf).resolve().relative_to(paths.ROOT.resolve()).as_posix()
    except ValueError:
        rel = Path(pdf).resolve().as_posix()
    when = draft.date
    try:
        when = dt.date.fromisoformat(draft.date).strftime("%d.%m.%Y")
    except ValueError:
        pass
    return {"title": f"Møteinnkalling {draft.body} {when} (saksdokumenter med vedlegg)",
            "url": f"local:{rel}"}


def to_agenda(draft: Draft, attachment: dict | None) -> dict:
    """The agenda as a dict that passes `agenda.Agenda`. Refuses an unconfirmed draft."""
    problems = []
    for it in draft.items:
        if it.closed is None:
            problems.append(f"{it.case_no}: choose closed yes/no")
        if it.in_scope is None:
            problems.append(f"{it.case_no}: choose in_scope yes/no")
        if it.name_flags:
            problems.append(f"{it.case_no}: title may contain a name or contact details "
                            f"({', '.join(it.name_flags)}); use a role instead")
    if not draft.items:
        problems.append("the agenda has no items")
    if problems:
        raise AgendaImportError("\n".join(problems))
    raw = {
        "meeting": {"id": draft.meeting_id, "body": draft.body,
                    "municipality": draft.municipality, "date": draft.date,
                    "written_standard": draft.written_standard},
        "items": [{"case_no": it.case_no, "type": it.type, "title": it.title,
                   "attachments": [dict(attachment)] if attachment else [],
                   "closed": it.closed, "in_scope": it.in_scope} for it in draft.items],
    }
    if draft.public_url:
        raw["meeting"]["public_url"] = draft.public_url
    from pydantic import ValidationError

    try:
        Agenda.model_validate(raw)
    except ValidationError as e:
        raise AgendaImportError("\n".join(
            f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())) from e
    return raw


def draft_yaml(draft: Draft, attachment: dict | None) -> str:
    """A draft agenda.yaml for the CLI: closed/in_scope are null and S0 rejects the file
    until a person fills them in."""
    import yaml

    head = ("# DRAFT from agenda import. Set every `closed` and `in_scope` (true/false),\n"
            "# check titles for names, then move the file into inbox/.\n")
    raw = {
        "meeting": {"id": draft.meeting_id, "body": draft.body,
                    "municipality": draft.municipality, "date": draft.date,
                    "written_standard": draft.written_standard},
        "items": [{"case_no": it.case_no, "type": it.type, "title": it.title,
                   "attachments": [dict(attachment)] if attachment else [],
                   "closed": None, "in_scope": None} for it in draft.items],
    }
    body = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False, width=100)
    notes = []
    for it in draft.items:
        if it.suggested_closed:
            notes.append(f"# {it.case_no}: marked closed in the saksliste "
                         "(suggest closed: true)")
        if it.name_flags:
            notes.append(f"# {it.case_no}: title flagged {', '.join(it.name_flags)}")
    body = body.replace("closed: null", "closed: null  # CONFIRM").replace(
        "in_scope: null", "in_scope: null  # CONFIRM")
    return head + ("\n".join(notes) + "\n" if notes else "") + body
