"""S6 — Item understanding (LLM).

Receives one agenda item and the glossary; never documents, other items or labels (§4.3).
"""

from __future__ import annotations

from .agenda import Item
from .llm import LLMClient
from .paths import context_text

SCHEMA = {
    "type": "object",
    "required": ["topic", "queries", "synonyms", "key_terms", "expected_document_types"],
    "properties": {
        "topic": {"type": "string"},
        "queries": {"type": "array", "minItems": 1, "maxItems": 12, "items": {
            "type": "object", "required": ["lang", "text"],
            "properties": {"lang": {"enum": ["nb", "nn", "en"]}, "text": {"type": "string"}}}},
        "synonyms": {"type": "array", "items": {"type": "string"}},
        "key_terms": {"type": "array", "items": {"type": "string"}},
        "expected_document_types": {"type": "array", "items": {"type": "string"}},
    },
}


def describe(item: Item) -> str:
    parts = [f"Case number: {item.case_no}", f"Type: {item.type.value}", f"Title: {item.title}"]
    if item.description:
        parts.append(f"Description: {item.description}")
    if item.recommendation:
        parts.append(f"Recommendation (innstilling): {item.recommendation}")
    parts.append("Attachments: " + (", ".join(a.title for a in item.attachments) or "none"))
    return "\n".join(parts)


def understand(item: Item, llm: LLMClient) -> dict:
    messages = [
        {"role": "system", "content": context_text("task_item_understanding.md")
            + "\n\n" + context_text("glossary_nb_nn_en.md")},
        {"role": "user", "content": "Agenda item:\n" + describe(item)
            + "\n\nReturn the JSON object now."},
    ]
    out = llm.complete_json("S6", messages, SCHEMA, item=item.case_no)
    # The title itself is always a query, whatever the model returns.
    out["queries"] = [{"lang": "orig", "text": item.title}] + out["queries"]
    return out
