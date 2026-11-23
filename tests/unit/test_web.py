import json

import pytest
from fastapi.testclient import TestClient

from briefer import assemble, paths
from briefer.web import app as webapp
from briefer.web import store

AGENDA = """\
meeting:
  id: m1
  body: "Fylkesutvalget"
  municipality: "Innlandet fylkeskommune"
  date: 2026-09-29
  written_standard: nb
items:
  - case_no: "PS 0/26"
    type: procedural
    title: "Godkjenning av innkalling og saksliste"
    closed: false
    in_scope: true
  - case_no: "PS 1/26"
    type: case
    title: "Budsjett"
    description: "Driftsrammen for neste år."
    attachments:
      - title: "Doc"
        url: "local:doc.pdf"
    closed: false
    in_scope: true
"""


@pytest.fixture
def client(tmp_path, monkeypatch, simple_pdf):
    runs = tmp_path / "runs"
    d = runs / "r1" / "m1" / "described"
    d.mkdir(parents=True)
    monkeypatch.setattr(paths, "RUNS", runs)
    monkeypatch.setattr(paths, "INBOX", tmp_path / "inbox")
    monkeypatch.setattr(paths, "INBOX_PENDING", tmp_path / "inbox" / "pending")
    monkeypatch.setattr(store, "DB", tmp_path / "t.sqlite")
    agenda = tmp_path / "agenda.yaml"
    agenda.write_text(AGENDA, encoding="utf-8")
    (d / "run_log.jsonl").write_text(json.dumps({
        "stage": "S6", "event": "understood", "case_no": "PS 1/26",
        "topic": "Operating budget frame", "queries": [
            {"lang": "orig", "text": "Budsjett"}, {"lang": "nb", "text": "driftsramme"},
            {"lang": "nn", "text": "driftsramme"}, {"lang": "en", "text": "operating budget"}]})
        + "\n", encoding="utf-8")
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
        "run_id": "r1", "meeting_id": "m1", "agenda": str(agenda), "style": "described",
        "brief_language": "nb",
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


def test_ui_language_switch(client):
    assert "Slik fungerer det" in client.get("/how").text
    client.cookies.set("ui_lang", "en")
    r = client.get("/how")
    assert "How it works" in r.text and 'lang="en"' in r.text
    client.cookies.set("ui_lang", "nn")
    assert "Slik verkar det" in client.get("/how").text


def test_meeting_shows_agenda_and_interpretation(client):
    r = client.get("/m/r1/m1/described")
    assert r.status_code == 200
    assert "Driftsrammen for neste år." in r.text  # agenda as read
    assert "Operating budget frame" in r.text  # S6 topic
    assert "nb·nn" in r.text and "operating budget" in r.text  # merged queries
    assert "written_standard: nb" in r.text  # raw agenda file


def test_meeting_without_agenda_file(client, tmp_path):
    (tmp_path / "agenda.yaml").unlink()
    r = client.get("/m/r1/m1/described")
    assert r.status_code == 200 and "ikke tilgjengelig" in r.text


def _upload(client, body: bytes, filename="min agenda.yaml"):
    return client.post("/upload", files={"file": (filename, body, "text/yaml")},
                       follow_redirects=False)


def test_upload_valid_previews_and_saves_normalised(client, tmp_path):
    r = _upload(client, AGENDA.encode())
    assert r.status_code == 303
    saved = list((tmp_path / "inbox" / "pending").iterdir())
    assert len(saved) == 1 and saved[0].name.startswith("upload_")
    assert saved[0].name.endswith("_m1.yaml") and "min" not in saved[0].name
    assert not list((tmp_path / "inbox").glob("*.yaml"))  # watcher cannot see it yet
    page = client.get(r.headers["location"]).text
    assert "Agendaen er gyldig" in page and "Nei – formalitet" in page


@pytest.mark.parametrize("body,name,msg", [
    (AGENDA.replace("    closed: false\n", "", 1).encode(), "a.yaml", "closed"),
    (b"meeting: [", "a.yaml", "cannot read agenda"),
    (AGENDA.encode(), "a.txt", ".yaml"),
    (b"#" * (200 * 1024 + 1), "a.yaml", "200 KB"),
    (b"\xff\xfe", "a.yml", "UTF-8"),
])
def test_upload_rejected_saves_nothing(client, tmp_path, body, name, msg):
    r = _upload(client, body, name)
    assert r.status_code == 400 and msg in r.text
    assert not (tmp_path / "inbox").exists() or not any((tmp_path / "inbox").rglob("*"))


def test_upload_start_runs_once(client, tmp_path, monkeypatch):
    from briefer import pipeline

    calls = []
    monkeypatch.setattr(pipeline, "run", lambda p, *a: calls.append(p) or {
        "run_id": "r2", "statuses": {}})
    loc = _upload(client, AGENDA.encode()).headers["location"]
    name = loc.rsplit("/", 1)[1]
    r = client.post(f"/upload/{name}/start", follow_redirects=False)
    assert r.status_code == 303
    moved = tmp_path / "inbox" / name
    assert moved.exists() and calls == [moved]
    assert pipeline.is_processed(moved)  # `watch` will skip it
    assert "Kjøringen er startet" in client.get(loc).text
    assert client.post(f"/upload/{name}/start").status_code == 404  # no second start


def test_upload_names_are_checked(client):
    assert client.get("/upload/..%2F..%2Fagenda.yaml").status_code in (400, 404)
    assert client.post("/upload/agenda.yaml/start").status_code == 400
    assert client.get("/upload/upload_20260101-000000_x.yaml").status_code == 404


def test_example_agenda_download(client):
    r = client.get("/example-agenda.yaml")
    assert r.status_code == 200 and "algorithms_synthetic" in r.text
