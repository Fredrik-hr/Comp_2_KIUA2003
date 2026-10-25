"""Data shared between stages. Everything here is serialisable to JSON."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Segment(BaseModel):
    id: str                       # doc_7f3a:p0142:s006
    doc_id: str
    page: int                     # physical page, 1-based (same as #page=N)
    seq: int                      # reading order within the document
    kind: str                     # body | heading | caption | table_row
    text: str                     # normalised text (text.normalize)
    section_path: list[str]
    table_header: str | None = None
    flags: list[str] = Field(default_factory=list)  # pii:<kind>, injection, hidden_text_removed


class Heading(BaseModel):
    text: str
    number: str | None
    level: int
    page: int
    offset: int                   # character offset in the normalised page text
    seq: int                      # seq of the heading segment


class PageInfo(BaseModel):
    page: int
    label: str | None
    label_source: str             # pdf_label | detected | none
    has_text_layer: bool
    hidden_chars_removed: int = 0


class ParsedDoc(BaseModel):
    doc_id: str
    sha256: str
    url: str
    title: str
    page_count: int
    pages: list[PageInfo]
    headings: list[Heading]
    segments: list[Segment]
    rejected: str | None = None   # set by S3 when the document is rejected for review

    def by_id(self) -> dict[str, Segment]:
        return {s.id: s for s in self.segments}


class XRef(BaseModel):
    source: str                   # segment id
    kind: str                     # section | chapter | figure | table | page | exercise | appendix
    label: str                    # the matched text, e.g. "Section 4.2"
    targets: list[str]            # segment ids


class Extract(BaseModel):
    segment_id: str
    text: str
    document_title: str
    source_url: str
    physical_page: int
    printed_page_label: str | None
    section_path: list[str]
    relevance: str
    found_via: str
    note: str
    table_header: str | None = None
