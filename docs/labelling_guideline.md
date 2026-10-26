# Labelling guideline

Gold labels say which passages a brief for an agenda item **must** contain. They are used
only by the evaluation harness (`eval/`); the pipeline never reads `labels/`.

## Order of work

1. Read the agenda item (title, description, recommendation).
2. Find the passages **before** looking at any system output for that meeting. Use
   `python eval/label.py find <meeting> "<phrase>"` to search the document text.
3. Add each passage with `python eval/label.py add …`. The helper refuses a quote that is not
   verbatim on the stated page (the gold labels pass V1).
4. For each item, record the expected outcome: `passages`, `nothing_found` or `skipped`.

## What counts as relevant (a gold passage)

A passage is gold if a participant preparing for the item would be misinformed or would have
to search the document themselves without it:

- the definition, explanation, decision, budget line or figure that the item is about;
- a passage the document points to from such a passage ("see Section 4.6", "jf. kap. 3")
  when the item cannot be understood without it — mark it `via: cross_reference`;
- the key result or statement (a theorem, a total, a resolution), not every sentence around it.

Not gold: the table of contents, the index, exercise lists, historical notes, or passages that
only mention the item's subject in passing.

## Subtopic tags (optional scheme)

A meeting can have a subtopic scheme (`Hovedtema:` line plus `Name: description` lines,
e.g. `docs/labels.txt` for PS 93/26, *Kjernekraft – naturvirkninger*). Store it once with
`python eval/label.py topics <agenda.yaml> <scheme.txt>`, then tag each passage with every
subtopic that fits: `add … --topic Arealbruk --topic "Vannmiljø og kjølevann"`. Unknown names
are refused. The report then shows recall per subtopic. The scheme is evaluation material:
it must never be copied into `context/` or a prompt.

## Granularity

- A gold passage is one paragraph, list item, table row, figure caption or algorithm box.
  Quote enough of it to be unique on the page (at least one full sentence), not the whole page.
- A passage that continues onto the next page is labelled once per page.
- Tables: label the rows that matter; the header is attached by the system automatically.

## Matching (how the harness scores)

A gold passage counts as found when at least 50% of its characters fall inside segments the
system selected (§3.3). Precision counts a selected segment as correct if it overlaps any gold
passage of the same item.

## Agreement

Both team members label the first real meeting independently. Agreement is measured as
segment-level F1 between annotators and Cohen's κ over the candidate segments
(`python eval/label.py agree <labels_a> <labels_b>`). Disagreements are discussed, this
guideline is updated, and the discussion goes in the meeting report.

## Status of `labels/algorithms_synthetic.yaml`

These labels were drafted by the coding agent from the document text before the pipeline was
run, following this guideline. They are **provisional**: a team member must review them and
change `reviewed_by` before they are reported as gold in the white paper.
