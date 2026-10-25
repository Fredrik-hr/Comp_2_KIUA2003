"""S0 — Load and gate.

Validates agenda.yaml strictly and decides which items are processed. `closed` and
`in_scope` have no defaults (§10.1): a missing value is a validation error, never a
silent "open, in scope".
"""

from __future__ import annotations

import datetime as dt
import logging
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

log = logging.getLogger(__name__)


class AgendaError(ValueError):
    """Raised for a malformed agenda.yaml. The message is shown to the organiser."""


class Strict(BaseModel):
    # extra="forbid" also rejects name fields such as `saksbehandler` (rule 2, §2.3).
    model_config = ConfigDict(extra="forbid", frozen=True)


class ItemType(StrEnum):
    procedural = "procedural"
    information = "information"
    case = "case"
    question = "question"


class Attachment(Strict):
    title: str
    url: str


class Item(Strict):
    case_no: str
    type: ItemType
    title: str = Field(min_length=1)
    description: str | None = None
    recommendation: str | None = None
    attachments: list[Attachment] = Field(default_factory=list)
    closed: bool
    in_scope: bool

    def titles_only(self) -> Item:
        """The agenda as published: titles only (rule 4, §2.3)."""
        return self.model_copy(update={"description": None, "recommendation": None})


class Meeting(Strict):
    id: str
    body: str
    municipality: str
    date: dt.date
    written_standard: str = Field(pattern="^(nb|nn)$")
    synthetic: bool = False


class Agenda(Strict):
    meeting: Meeting
    items: list[Item]

    @field_validator("items")
    @classmethod
    def unique_case_numbers(cls, items: list[Item]) -> list[Item]:
        seen = [i.case_no for i in items]
        dupes = {c for c in seen if seen.count(c) > 1}
        if dupes:
            raise ValueError(f"duplicate case_no: {sorted(dupes)}")
        return items


class Gate(BaseModel):
    item: Item
    process: bool
    skip_reason: str | None = None


def load(path: Path) -> Agenda:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise AgendaError(f"{path}: cannot read agenda: {e}") from e
    if not isinstance(raw, dict):
        raise AgendaError(f"{path}: agenda must be a mapping with `meeting` and `items`")
    try:
        return Agenda.model_validate(raw)
    except ValidationError as e:
        lines = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        raise AgendaError(f"{path}: invalid agenda:\n  " + "\n  ".join(lines)) from e


def gate(item: Item) -> Gate:
    if item.closed:
        reason = "closed item (lukket sak) — never processed"
    elif item.type is ItemType.procedural:
        reason = "procedural item"
    elif not item.in_scope:
        reason = "marked out of scope (in_scope: false)"
    else:
        return Gate(item=item, process=True)
    log.info("S0 skip %s: %s", item.case_no, reason)
    return Gate(item=item, process=False, skip_reason=reason)
