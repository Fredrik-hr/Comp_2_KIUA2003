from eval.summarize import summarize_run

MARKER = "SECRET TEXT p.650"

RESULTS = {
    "llm_mode": "replay",
    "llm_config": {"S8": {"model": "qwen2.5:7b", "strategy": "pointwise"}},
    "cases": {"meeting": {"described": {
        "summary": {"extracts_failed": 2, "extracts_checked": 119, "llm_calls": 227},
        "aggregate": {"items": 1, "gold_passages": 40, "found": 4, "selected": 20,
                      "recall_micro": 0.1, "precision_micro": 0.2,
                      "found_by_topic": {"Arealbruk": [0, 15]}},
        "items": [{"case_no": "PS 93/26", "expect": "passages", "status": "awaiting_review",
                   "n_gold": 40, "n_found": 4, "n_selected": 20, "recall": 0.1,
                   "precision": 0.2,
                   "missed": [{"quote": MARKER}],
                   "false_positives": [{"segment_id": "doc:p1:s1", "text": MARKER}],
                   "removed": [{"segment_id": "doc:p2:s2", "failures": [MARKER]}]}],
    }}},
    "rejected_input": [{"case": "name_field.yaml", "rejected": True, "error": MARKER}],
}


def test_numbers_and_ids_are_reported():
    md = summarize_run("20261028-000000", RESULTS)
    assert "PS 93/26" in md and "0.10" in md and "2/119" in md and "0/15" in md
    assert "name_field.yaml ✓" in md


def test_no_document_text_leaks():
    md = summarize_run("20261028-000000", RESULTS)
    assert MARKER not in md
    assert "doc:p1:s1" not in md and "doc:p2:s2" not in md
