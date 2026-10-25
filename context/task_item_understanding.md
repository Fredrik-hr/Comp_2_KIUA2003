# Task: understand one agenda item (stage S6)

You receive ONE agenda item from a Norwegian public meeting: its title, and sometimes a
description and a recommendation (innstilling). Often the title is all there is.

Your job is to help a search engine find every passage in the attached documents that
the item is about. You do not answer the item, summarise it, or judge it.

Return JSON with:

- `topic`: one short sentence in English saying what the item is about.
- `queries`: 4–8 short keyword search queries (2–6 words each). The attached documents may
  be written in bokmål, nynorsk or English, so write queries in **all three**:
  - `nb`: bokmål, `nn`: nynorsk, `en`: English.
  - Use the technical terms a document on this subject would use, not the agenda's wording only.
- `synonyms`: alternative terms, abbreviations and spelling variants (e.g. skole/skule,
  vedtatt/vedteke, shortest path/korteste vei).
- `key_terms`: names of budget areas, projects, roads, algorithms, laws or programmes the item
  names or clearly implies.
- `expected_document_types`: e.g. budget, economic plan, regional plan, textbook chapter.

Why: agenda titles are short and often use different words from the documents. Searching in
several languages and with domain terms is what lets the next stage find passages spread
across distant chapters.

Use the glossary for standard term pairs. Do not invent facts, numbers or document content.
