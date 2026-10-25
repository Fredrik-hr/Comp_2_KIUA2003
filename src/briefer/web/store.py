"""Review state and audit log (SQLite). No user accounts; actions are logged by role."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from contextlib import closing

from .. import paths

DB = paths.ROOT / "briefer.sqlite"
ROLE = "organiser"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        brief TEXT PRIMARY KEY, state TEXT NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit (
        id INTEGER PRIMARY KEY, t TEXT, role TEXT, brief TEXT, action TEXT, detail TEXT)""")
    return c


def get_state(brief_key: str, brief: dict) -> dict:
    with closing(_conn()) as c:
        row = c.execute("SELECT state FROM reviews WHERE brief=?", (brief_key,)).fetchone()
    if row:
        return json.loads(row[0])
    return {"order": [e["segment_id"] for e in brief["extracts"]], "removed": [],
            "organiser_note": "", "language": brief["brief_language"],
            "status": brief["status"]}


def save_state(brief_key: str, state: dict, action: str, detail: str = "") -> None:
    with closing(_conn()) as c, c:
        c.execute("INSERT OR REPLACE INTO reviews (brief, state) VALUES (?, ?)",
                  (brief_key, json.dumps(state, ensure_ascii=False)))
        c.execute("INSERT INTO audit (t, role, brief, action, detail) VALUES (?,?,?,?,?)",
                  (dt.datetime.now().isoformat(timespec="seconds"), ROLE, brief_key, action,
                   detail[:500]))


def audit(brief_key: str) -> list[tuple]:
    with closing(_conn()) as c:
        return c.execute("SELECT t, role, action, detail FROM audit WHERE brief=? ORDER BY id",
                         (brief_key,)).fetchall()
