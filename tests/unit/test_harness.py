from types import SimpleNamespace as NS

from eval.harness import missing_sources


def _item(url, closed=False, in_scope=True):
    return NS(closed=closed, in_scope=in_scope, attachments=[NS(url=url)])


def test_missing_local_source_is_reported():
    agenda = NS(items=[_item("local:does_not_exist.pdf")])
    assert missing_sources(agenda) == ["does_not_exist.pdf"]


def test_closed_out_of_scope_and_remote_items_are_ignored():
    agenda = NS(items=[
        _item("local:closed_missing.pdf", closed=True),
        _item("local:out_of_scope_missing.pdf", in_scope=False),
        _item("https://example.org/doc.pdf"),
    ])
    assert missing_sources(agenda) == []
