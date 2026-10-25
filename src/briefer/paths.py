"""Project paths and config loading. Pipeline code reads inbox/, data/raw/ and context/,
and writes only data/derived/ and runs/ (§8.1)."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("BRIEFER_ROOT", Path(__file__).resolve().parents[2]))
CONFIG = ROOT / "config"
CONTEXT = ROOT / "context"
INBOX = ROOT / "inbox"
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
LLM_CACHE = ROOT / "data" / "llm_cache"
RUNS = ROOT / "runs"


@cache
def config(name: str) -> dict:
    return yaml.safe_load((CONFIG / f"{name}.yaml").read_text(encoding="utf-8"))


def context_text(name: str) -> str:
    return (CONTEXT / name).read_text(encoding="utf-8")
