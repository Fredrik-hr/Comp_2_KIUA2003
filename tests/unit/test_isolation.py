"""Rule 1 (§2.3): the pipeline has no code path to labels/."""

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "briefer"


def test_pipeline_never_references_labels_dir():
    offenders = []
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if re.search(r"""["'/\\]labels\b|\blabels/|LABELS""", text):
            offenders.append(str(py.relative_to(SRC)))
    assert offenders == []


def test_pipeline_does_not_import_eval():
    for py in SRC.rglob("*.py"):
        assert not re.search(r"^\s*(from|import)\s+eval\b", py.read_text(encoding="utf-8"),
                             re.M), py
