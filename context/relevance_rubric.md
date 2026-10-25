# Relevance rubric (stage S8)

You choose which document segments belong in the brief for ONE agenda item. A person reads
the brief before the meeting instead of searching hundreds of pages. A missed relevant
passage is worse than an extra one: the organiser can delete extras, but cannot see what
you missed. Still, do not select segments that are only loosely on the same broad subject.

Each selected segment gets one relevance label:

- `direct`: the segment is about exactly what the item is about — it defines, describes,
  decides, budgets or explains the item's subject.
  - nb: «Driftsrammen for videregående opplæring økes med 12,3 mill. kr» for an item on the
    school budget.
  - en: "The Bellman-Ford algorithm updates all the edges |V|-1 times" for an item on shortest
    paths with negative edges.
- `supporting`: needed to understand a direct passage: a definition it relies on, the table
  row it refers to, a premise, a figure caption, the continuation of the same explanation.
- `cross_reference`: a segment the document itself points to from a direct passage
  ("jf. kap. 4.2", "see Section 4.6", "se tabell 3"). Candidates marked `via xref` came this way.

Do NOT select:
- segments that only share a word with the item but are about something else;
- tables of contents, index pages, headers, exercise lists unless the item is about them;
- the same passage twice.

When to return `nothing_found`: when no candidate is about the item's subject — for example
the item is about road maintenance contracts and the documents are about something else
entirely. Returning `nothing_found` is a correct, valuable answer. Never select segments just
to have something.

The note for each segment is ONE line saying why it is relevant, in the requested brief
language. Do not put numbers in the note unless they appear in that segment — no case
numbers, page numbers or section numbers. Do not summarise or interpret beyond that one line.
