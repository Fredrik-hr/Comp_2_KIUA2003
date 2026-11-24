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
    monkeypatch.setattr(paths, "UPLOADS", tmp_path / "uploads")
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


# --- møteinnkalling (PDF / Word) -> draft -> pending agenda ------------------------------

def _innkalling(tmp_path):
    from .conftest import make_pdf

    lines = ["Utvalg:", "Fylkesutvalget", "Dato:", "29.09.2026", "Testvik fylkeskommune",
             "PS 1/26", "Budsjett", "PS 2/26", "Kjøp av eiendom", "X", "PS = Politisk sak"]
    return make_pdf(tmp_path / "innkalling.pdf", [[(x, 11, False, (0, 0, 0)) for x in lines]])


def _upload_pdf(client, pdf):
    with open(pdf, "rb") as f:
        return client.post("/upload", files={"file": ("innkalling.pdf", f, "application/pdf")},
                           follow_redirects=False)


def _draft_form(handling=("process", "closed")):
    data = {"n": "2", "body": "Fylkesutvalget", "municipality": "Testvik fylkeskommune",
            "date": "2026-09-29", "meeting_id": "fylkesutvalget_2026-09-29",
            "written_standard": "nb"}
    for i, (case_no, title) in enumerate([("PS 1/26", "Budsjett"),
                                          ("PS 2/26", "Kjøp av eiendom")]):
        data |= {f"case_no_{i}": case_no, f"title_{i}": title, f"type_{i}": "case"}
        if handling[i]:
            data[f"handling_{i}"] = handling[i]
    return data


def test_pdf_upload_draft_confirm_goes_to_pending(client, tmp_path):
    r = _upload_pdf(client, _innkalling(tmp_path))
    assert r.status_code == 303 and r.headers["location"].startswith("/upload/draft/")
    draft = client.get(r.headers["location"])
    assert draft.status_code == 200
    assert "Kontroller sakslisten" in draft.text and "Kjøp av eiendom" in draft.text
    assert draft.text.count('value="" selected disabled') == 2  # no handling pre-selected
    assert "Foreslått: Lukket sak" in draft.text  # but the "X" in UOFF is suggested
    r = client.post(r.headers["location"], data=_draft_form(), follow_redirects=False)
    assert r.status_code == 303
    name = r.headers["location"].rsplit("/", 1)[1]
    pending = tmp_path / "inbox" / "pending" / name
    assert pending.exists() and not list((tmp_path / "inbox").glob("*.yaml"))
    from briefer.agenda import load

    agenda = load(pending)
    assert [i.closed for i in agenda.items] == [False, True]
    assert agenda.items[0].attachments[0].url.endswith("innkalling.pdf")
    page = client.get(r.headers["location"]).text
    assert "Agendaen er gyldig" in page and "Start kjøring" in page


def test_draft_without_closed_is_refused(client, tmp_path):
    loc = _upload_pdf(client, _innkalling(tmp_path)).headers["location"]
    r = client.post(loc, data=_draft_form(handling=("process", "")))
    assert r.status_code == 400 and "PS 2/26: velg behandling." in r.text
    assert "choose closed" not in r.text
    assert not (tmp_path / "inbox").exists()
    # an unknown value counts as no choice
    r = client.post(loc, data=_draft_form(handling=("process", "maybe")))
    assert r.status_code == 400 and "PS 2/26: velg behandling." in r.text


@pytest.mark.parametrize("handling,closed,in_scope", [
    ("process", False, True), ("closed", True, False), ("out_of_scope", False, False)])
def test_handling_maps_to_closed_and_in_scope(client, tmp_path, handling, closed, in_scope):
    from briefer.agenda import load

    loc = _upload_pdf(client, _innkalling(tmp_path)).headers["location"]
    r = client.post(loc, data=_draft_form(handling=(handling, "leave_out")),
                    follow_redirects=False)
    assert r.status_code == 303
    agenda = load(tmp_path / "inbox" / "pending" / r.headers["location"].rsplit("/", 1)[1])
    assert [(i.case_no, i.closed, i.in_scope) for i in agenda.items] == [
        ("PS 1/26", closed, in_scope)]  # the left-out row is not written at all


def test_draft_with_name_in_title_is_refused(client, tmp_path):
    loc = _upload_pdf(client, _innkalling(tmp_path)).headers["location"]
    form = _draft_form() | {"title_1": "Spørsmål fra Kari Nordmann om skolebuss"}
    r = client.post(loc, data=form)
    assert r.status_code == 400 and "pii:name" in r.text
    assert not (tmp_path / "inbox").exists()


def test_bad_documents_and_tokens_refused(client, tmp_path):
    r = client.post("/upload", files={"file": ("a.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 400 and "gyldig PDF" in r.text
    assert client.get("/upload/draft/..%2Fsecret.pdf").status_code in (400, 404)
    assert client.get("/upload/draft/x.yaml").status_code == 400
    assert client.get("/upload/draft/abc_missing.pdf").status_code == 404


def test_draft_requires_passphrase(client, monkeypatch):
    monkeypatch.setenv("BRIEFER_UI_PASSPHRASE", "hemmelig")
    r = client.get("/upload/draft/abc.pdf", follow_redirects=False)
    assert r.status_code == 303
    r = client.post("/upload/draft/abc.pdf", data=_draft_form(), follow_redirects=False)
    assert r.status_code == 303


# --- why block and orientation view ------------------------------------------------------

def _with_why(tmp_path):
    """Give the fixture brief the new why-fields, as a fresh run would."""
    p = tmp_path / "runs" / "r1" / "m1" / "described" / "PS_1_26.json"
    brief = json.loads(p.read_text(encoding="utf-8"))
    e1, e2 = brief["extracts"]
    e1 |= {"category": "consequences", "matched_query": "driftsramme",
           "matched_terms": ["Driftsrammen"]}
    e2 |= {"category": "decision", "found_via": "innstilling", "note": "",
           "text": "1. Fylkesutvalget vedtar budsjettet. " + "Lang begrunnelse følger. " * 20}
    p.write_text(json.dumps(brief), encoding="utf-8")


def test_item_page_shows_why_and_highlight(client, tmp_path):
    _with_why(tmp_path)
    page = client.get(BASE).text
    assert "Hvorfor dette utdraget?" in page
    assert "<mark>Driftsrammen</mark> er 1 234,5" in page
    assert "Konsekvenser · fra samme del av dokumentet som et treff på «driftsramme»" in page \
        or "Konsekvenser · treff på søket «driftsramme»" in page
    assert "funnet av koden i innstillingen til vedtak" in page
    assert "Maskinskrevet merknad: Ramme." in page   # the model note is kept, labelled
    # the extract text itself is never altered
    out = json.loads((tmp_path / "runs" / "r1" / "m1" / "described" / "PS_1_26.json")
                     .read_text(encoding="utf-8"))
    assert out["extracts"][0]["text"] == "Driftsrammen er 1 234,5 mill. kr."


def test_item_page_without_why_fields(client):
    page = client.get(BASE).text   # fixture extracts have no category / query
    assert page.count("Hvorfor dette utdraget?") == 2   # both fixture extracts have a note
    assert "treff på søket" not in page and "chip cat" not in page  # no code facts to show
    assert "Direkte relevant" in page


def test_orientation_groups_decision_first_and_shortens(client, tmp_path):
    _with_why(tmp_path)
    r = client.get("/o/r1/m1/described")
    assert r.status_code == 200
    page = r.text
    assert page.index("Hva skal vedtas") < page.index("Konsekvenser")
    assert "Ikke godkjent ennå" in page
    assert "1. Fylkesutvalget vedtar budsjettet." in page and "Vis hele utdraget" in page
    client.post(BASE + "/action", data={"op": "remove",
                                        "segment_id": "doc_abababab:p0001:s002"})
    client.post(BASE + "/action", data={"op": "approve"})
    page = client.get("/o/r1/m1/described").text
    assert "Konsekvenser" not in page       # removed in review -> not in orientation
    assert "Ikke godkjent ennå" not in page


def test_orientation_link_and_auth(client, monkeypatch):
    assert 'href="/o/r1/m1/described"' in client.get("/m/r1/m1/described").text
    assert client.get("/o/..%2F..%2Fx/m1/described").status_code in (400, 404)
    monkeypatch.setenv("BRIEFER_UI_PASSPHRASE", "hemmelig")
    assert client.get("/o/r1/m1/described", follow_redirects=False).status_code == 303


# --- meeting brief PDF -------------------------------------------------------------------

def _add_closed_item(tmp_path):
    d = tmp_path / "runs" / "r1" / "m1" / "described"
    closed = {"case_no": "PS 9/26", "title": "Hemmelig personalsak", "meeting_id": "m1",
              "status": "skipped", "skip_reason": "closed item (lukket sak) — never processed",
              "brief_language": "nb", "extracts": [], "run_id": "r1",
              "verification": {"all_passed": True, "checks": []},
              "disclaimer": assemble.DISCLAIMER["nb"]}
    (d / "PS_9_26.json").write_text(json.dumps(closed), encoding="utf-8")
    run = json.loads((d / "run.json").read_text(encoding="utf-8"))
    run["statuses"]["PS 9/26"] = "skipped"
    (d / "run.json").write_text(json.dumps(run), encoding="utf-8")


def _pdf_text(content: bytes) -> str:
    import fitz

    doc = fitz.open(stream=content, filetype="pdf")
    return "".join(p.get_text() for p in doc)


EXPORT = "/m/r1/m1/described/export"


def test_export_blocked_until_reviewed(client, tmp_path):
    _add_closed_item(tmp_path)
    page = client.get(EXPORT).text
    assert "må godkjennes eller avvises" in page and "disabled" in page
    r = client.post(EXPORT + ".pdf", data={"language": "nb", "confirm_pii": "yes"})
    assert r.status_code == 409


def test_export_requires_pii_confirmation(client, tmp_path):
    client.post(BASE + "/action", data={"op": "approve"})
    r = client.post(EXPORT + ".pdf", data={"language": "nb"})
    assert r.status_code == 400
    assert not [a for a in store.audit("r1/m1/described/_meeting") if a[2] == "export_meeting"]


def test_export_pdf_contents_and_audit(client, tmp_path):
    _with_why(tmp_path)
    _add_closed_item(tmp_path)
    client.post(BASE + "/action", data={"op": "note", "note": "Les side 1."})
    client.post(BASE + "/action", data={"op": "approve"})
    assert "Alle behandlede saker er godkjent" in client.get(EXPORT).text
    r = client.post(EXPORT + ".pdf", data={"language": "nb", "confirm_pii": "yes",
                                           "note": "Møtet starter kl. 12."})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert 'filename="m1_brief.pdf"' in r.headers["content-disposition"]
    text = _pdf_text(r.content)
    assert "Brief til møtet" in text and "Fylkesutvalget" in text
    assert "PS 9/26" in text and "lukket sak" in text
    assert "Hemmelig personalsak" not in text             # never the title of a closed item
    assert "Hva skal vedtas" in text and "Konsekvenser" in text
    assert "Driftsrammen er 1 234,5 mill. kr." in text    # verbatim
    assert "Møtet starter kl. 12." in text and "Les side 1." in text
    assert "Vedlegg: alle utdrag" in text
    assert "side 1 av" in text
    log = store.audit("r1/m1/described/_meeting")
    assert log[-1][1:3] == ("organiser", "export_meeting")
    assert "personal data checked" in log[-1][3]
    assert "Møtet starter kl. 12." in client.get(EXPORT).text   # note remembered


def test_export_rejected_item_is_listed_as_no_brief(client, tmp_path):
    client.post(BASE + "/action", data={"op": "reject"})
    r = client.post(EXPORT + ".pdf", data={"language": "en", "confirm_pii": "yes"})
    text = _pdf_text(r.content)
    assert "Meeting brief" in text and "PS 1/26" in text and "no brief" in text
    assert "Driftsrammen" not in text


def test_export_auth_and_link(client, monkeypatch):
    assert f'href="{EXPORT}"' in client.get("/m/r1/m1/described").text
    monkeypatch.setenv("BRIEFER_UI_PASSPHRASE", "hemmelig")
    assert client.get(EXPORT, follow_redirects=False).status_code == 303
    r = client.post(EXPORT + ".pdf", data={"confirm_pii": "yes"}, follow_redirects=False)
    assert r.status_code == 303


def test_public_url_from_draft_reaches_agenda(client, tmp_path):
    from briefer.agenda import load

    loc = _upload_pdf(client, _innkalling(tmp_path)).headers["location"]
    form = _draft_form() | {"public_url": "https://example.no/moter/1"}
    r = client.post(loc, data=form, follow_redirects=False)
    agenda = load(tmp_path / "inbox" / "pending" / r.headers["location"].rsplit("/", 1)[1])
    assert agenda.meeting.public_url == "https://example.no/moter/1"
    bad = _draft_form() | {"public_url": "javascript:alert(1)"}
    assert client.post(loc, data=bad).status_code == 400
