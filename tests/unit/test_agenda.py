import logging

import pytest
import yaml

from briefer.agenda import AgendaError, gate, load

BASE = {
    "meeting": {"id": "m1", "body": "Fylkesutvalget", "municipality": "Innlandet fylkeskommune",
                "date": "2026-11-05", "written_standard": "nb"},
    "items": [
        {"case_no": "PS 1/26", "type": "case", "title": "Budsjett 2027",
         "attachments": [{"title": "Budsjett", "url": "local:x.pdf"}],
         "closed": False, "in_scope": True},
    ],
}


def write(tmp_path, data):
    p = tmp_path / "agenda.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def item(**over):
    d = dict(BASE["items"][0])
    d.update(over)
    return {**BASE, "items": [d]}


def test_valid_agenda_loads(tmp_path):
    a = load(write(tmp_path, BASE))
    assert a.items[0].case_no == "PS 1/26"
    assert gate(a.items[0]).process


def test_closed_item_is_skipped_and_logged(tmp_path, caplog):
    a = load(write(tmp_path, item(closed=True)))
    with caplog.at_level(logging.INFO):
        g = gate(a.items[0])
    assert not g.process and "closed" in g.skip_reason
    assert "PS 1/26" in caplog.text


def test_procedural_and_out_of_scope_skipped(tmp_path):
    assert not gate(load(write(tmp_path, item(type="procedural"))).items[0]).process
    assert not gate(load(write(tmp_path, item(in_scope=False))).items[0]).process


@pytest.mark.parametrize("field", ["closed", "in_scope"])
def test_missing_gate_field_is_rejected_not_defaulted(tmp_path, field):
    data = item()
    del data["items"][0][field]
    with pytest.raises(AgendaError, match=field):
        load(write(tmp_path, data))


def test_name_field_saksbehandler_rejected(tmp_path):
    with pytest.raises(AgendaError, match="saksbehandler"):
        load(write(tmp_path, item(saksbehandler="Kari Nordmann")))


def test_wrong_types_and_garbage_rejected(tmp_path):
    with pytest.raises(AgendaError):
        load(write(tmp_path, item(closed="maybe")))
    p = tmp_path / "bad.yaml"
    p.write_text("meeting: [unclosed", encoding="utf-8")
    with pytest.raises(AgendaError):
        load(p)


def test_duplicate_case_numbers_rejected(tmp_path):
    data = {**BASE, "items": BASE["items"] * 2}
    with pytest.raises(AgendaError, match="duplicate"):
        load(write(tmp_path, data))


def test_titles_only_strips_description(tmp_path):
    a = load(write(tmp_path, item(description="Mer tekst", recommendation="Vedtas")))
    t = a.items[0].titles_only()
    assert t.description is None and t.recommendation is None and t.title == "Budsjett 2027"
