"""S1 — Fetch and cache.

Downloads attachments from allowlisted domains only, or reads `local:<path>` files for
tests. Stores each document read-only under data/raw/<sha256>.pdf, so a document shared
by several items is fetched and parsed once.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import paths

log = logging.getLogger(__name__)


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Fetched:
    url: str
    sha256: str
    path: Path

    @property
    def doc_id(self) -> str:
        return f"doc_{self.sha256[:8]}"


def _allowed(host: str) -> bool:
    allowed = paths.config("sources")["allowed_domains"]
    host = host.lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def resolve_local(url: str) -> Path:
    rel = url.removeprefix("local:")
    for root in paths.config("sources")["local_roots"]:
        p = (paths.ROOT / root / rel).resolve()
        if p.is_file():
            return p
    raise FetchError(f"local document not found: {rel}")


def _store(data: bytes) -> tuple[str, Path]:
    sha = hashlib.sha256(data).hexdigest()
    paths.RAW.mkdir(parents=True, exist_ok=True)
    target = paths.RAW / f"{sha}.pdf"
    if not target.exists():
        target.write_bytes(data)
        os.chmod(target, stat.S_IREAD)  # data/raw/ is read-only after fetch (§8.1)
    return sha, target


def fetch(url: str, client: httpx.Client | None = None) -> Fetched:
    if url.startswith("local:"):
        data = resolve_local(url).read_bytes()
    else:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or not _allowed(parsed.hostname):
            raise FetchError(f"refused: {url} is not on the allowlist in config/sources.yaml")
        limit = paths.config("sources")["max_download_mb"] * 1024 * 1024
        own = client is None
        client = client or httpx.Client(timeout=60, follow_redirects=False)
        try:
            resp = client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise FetchError(f"download failed: {url}: {e}") from e
        finally:
            if own:
                client.close()
        if len(resp.content) > limit:
            raise FetchError(f"refused: {url} exceeds {limit} bytes")
        data = resp.content
    if not data.startswith(b"%PDF"):
        raise FetchError(f"not a PDF: {url}")
    sha, path = _store(data)
    log.info("S1 %s -> %s", url, path.name)
    return Fetched(url=url, sha256=sha, path=path)


class Fetcher:
    """Deduplicates by URL within a run; content dedup happens via the sha256 cache."""

    def __init__(self) -> None:
        self._by_url: dict[str, Fetched | FetchError] = {}

    def get(self, url: str) -> Fetched:
        if url not in self._by_url:
            try:
                self._by_url[url] = fetch(url)
            except FetchError as e:
                self._by_url[url] = e
        result = self._by_url[url]
        if isinstance(result, FetchError):
            raise result
        return result
