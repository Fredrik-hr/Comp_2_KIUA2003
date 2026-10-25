"""Kill switch (§8.5). Checked between every stage and every item."""

from __future__ import annotations

import os

from . import paths


class KillSwitch(RuntimeError):
    def __init__(self, condition: int, reason: str) -> None:
        super().__init__(f"kill switch condition {condition}: {reason}")
        self.condition = condition
        self.reason = reason


def check_stop() -> None:
    """Condition 5: STOP file or BRIEFER_DISABLED=1."""
    cfg = paths.config("killswitch")
    if (paths.ROOT / cfg["stop_file"]).exists():
        raise KillSwitch(5, f"{cfg['stop_file']} file present in project root")
    if os.environ.get(cfg["disable_env"], "0") not in ("", "0"):
        raise KillSwitch(5, f"{cfg['disable_env']} is set")


def check_failed_ratio(checked: int, failed: int) -> None:
    """Condition 1: too many selected extracts fail V1–V5."""
    cfg = paths.config("killswitch")
    if checked >= cfg["min_extracts_for_ratio"] and failed / checked > cfg[
            "max_failed_extract_ratio"]:
        raise KillSwitch(1, f"{failed} of {checked} extracts failed V1-V5 "
                            f"(> {cfg['max_failed_extract_ratio']:.0%})")


def check_llm_failures(consecutive: int) -> None:
    """Condition 3: consecutive failed or invalid LLM calls."""
    limit = paths.config("killswitch")["max_consecutive_llm_failures"]
    if consecutive >= limit:
        raise KillSwitch(3, f"{consecutive} consecutive LLM calls failed or returned invalid JSON")


def check_injection(selected_flags: dict[str, list[str]]) -> None:
    """Condition 4: the agent selected a segment flagged with an injection pattern."""
    hits = [sid for sid, flags in selected_flags.items() if "injection" in flags]
    if hits:
        raise KillSwitch(4, f"agent output references injection-flagged segments {hits}")
