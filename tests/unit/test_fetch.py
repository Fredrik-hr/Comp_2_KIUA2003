import pytest

from briefer import fetch, paths


def test_non_allowlisted_url_refused(tmp_data):
    with pytest.raises(fetch.FetchError, match="allowlist"):
        fetch.fetch("https://evil.example.com/doc.pdf")
    with pytest.raises(fetch.FetchError, match="allowlist"):
        fetch.fetch("http://innlandetfylke.no/doc.pdf")  # https only


def test_allowlist_matches_subdomains_only():
    assert fetch._allowed("innlandetfylke.no")
    assert fetch._allowed("www.innlandetfylke.no")
    assert not fetch._allowed("innlandetfylke.no.evil.com")
    assert not fetch._allowed("notinnlandetfylke.no")


def test_same_document_cached_once(tmp_data, simple_pdf, monkeypatch):
    monkeypatch.setattr(fetch, "resolve_local", lambda url: simple_pdf)
    a = fetch.fetch("local:a.pdf")
    b = fetch.fetch("local:b.pdf")  # same bytes, different name
    assert a.sha256 == b.sha256 and a.path == b.path
    assert len(list(paths.RAW.iterdir())) == 1


def test_non_pdf_refused(tmp_data, tmp_path, monkeypatch):
    junk = tmp_path / "x.pdf"
    junk.write_bytes(b"not a pdf at all")
    monkeypatch.setattr(fetch, "resolve_local", lambda url: junk)
    with pytest.raises(fetch.FetchError, match="not a PDF"):
        fetch.fetch("local:x.pdf")
