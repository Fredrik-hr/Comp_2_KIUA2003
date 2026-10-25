import json

import pytest
from fastapi.testclient import TestClient

from briefer import assemble, paths
from briefer.web import app as webapp
from briefer.web import store


@pytest.fixture
def client(tmp_path, monkeypatch, simple_pdf):
    runs = tmp_path / "runs"
    d = runs / "r1" / "m1" / "described"
    d.mkdir(parents=True)
    monkeypatch.setattr(paths, "RUNS", runs)
    monkeypatch.setattr(store, "DB", tmp_path / "t.sqlite")
    monkeypatch.delenv("BRIEFER_UI_PASSPHRASE", raising=False)
    ex = {"segment_id": "doc_abababab:p0001:s002", "text": "Driftsrammen er 1 234,5 mill. kr.",
          "document_title": "Doc", "source_url": "local:doc.pdf#page=1", "physical_page": 1,
          "printed_page_label": "1", "section_path": ["4 Driftsbudsjett"],
          "relevance": "direct", "found_via": "search", "note": "Ramme.", "table_header": None}
    ex2 = {**ex, "segment_id": "doc_abababab:p0001:s003", "text": "Annen tekst."}
    brief = {"case_no": "PS 1/26", "title": "Budsjett", "meeting_id": "m1",
             "status": "awaiting_review", "brief_language": "nb", "extracts": [ex, ex2],
             "verification": {"all_passed": True, "checks": ["V1-V5: 2/2"]}, "run_id": "r1",
             "disclaimer": assemble.DISCLAIMER["nb"]}
    (d / "PS_1_26.json").write_text(json.dumps(brief), encoding="utf-8")
    (d / "run.json").write_text(json.dumps({
        "run_id": "r1", "meeting_id": "m1", "style": "described", "brief_language": "nb",
        "statuses": {"PS 1/26": "awaiting_review"}, "halted": None, "llm_calls": 2,
        "tokens": 10, "seconds": 1,
        "documents": {"doc_abababab": {"path": str(simple_pdf), "title": "Doc"}}}),
        encoding="utf-8")
    return TestClient(webapp.app)


BASE = "/i/r1/m1/described/PS_1_26"


def test_pages_render(client):
    assert "m1" in client.get("/").text
    assert "PS 1/26" in client.get("/m/r1/m1/described").text
    r = client.get(BASE)
    assert r.status_code == 200 and "1 234,5" in r.text
    png = client.get("/page/r1/m1/described/doc_abababab/1.png")
    assert png.headers["content-type"] == "image/png"


def test_export_only_after_approval(client):
    assert client.get("/export/r1/m1/described/PS_1_26.html").status_code == 403
    client.post(BASE + "/action", data={"op": "approve"})
    r = client.get("/export/r1/m1/described/PS_1_26.html")
    assert r.status_code == 200 and "1 234,5" in r.text


def test_remove_reorder_language_and_audit(client):
    client.post(BASE + "/action", data={"op": "down", "segment_id": "doc_abababab:p0001:s002"})
    client.post(BASE + "/action", data={"op": "remove", "segment_id": "doc_abababab:p0001:s003"})
    client.post(BASE + "/action", data={"op": "language", "language": "en"})
    client.post(BASE + "/action", data={"op": "approve"})
    out = client.get("/export/r1/m1/described/PS_1_26.json").json()
    assert [e["segment_id"] for e in out["extracts"]] == ["doc_abababab:p0001:s002"]
    assert out["disclaimer"] == assemble.DISCLAIMER["en"]
    assert out["extracts"][0]["text"] == "Driftsrammen er 1 234,5 mill. kr."  # never altered
    log = store.audit("r1/m1/described/PS_1_26")
    assert [a[2] for a in log][:4] == ["down", "remove", "language", "approve"]
    assert all(a[1] == "organiser" for a in log)  # role, never a name


def test_edit_after_approval_requires_new_approval(client):
    client.post(BASE + "/action", data={"op": "approve"})
    client.post(BASE + "/action", data={"op": "note", "note": "Les side 1."})
    assert client.get("/export/r1/m1/described/PS_1_26.html").status_code == 403


def test_path_traversal_refused(client):
    assert client.get("/m/..%2F..%2Fetc/m1/described").status_code in (400, 404)
    assert client.get("/i/r1/m1/described/..").status_code in (400, 404)


def test_passphrase(client, monkeypatch):
    monkeypatch.setenv("BRIEFER_UI_PASSPHRASE", "hemmelig")
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303
    client.post("/login", data={"passphrase": "hemmelig"})
    assert client.get("/").status_code == 200
