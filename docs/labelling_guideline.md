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

A meeting can have a subtopic scheme: a YAML file with a `hovedtema:` key and one
`Name: description` entry per subtopic under `underemner:`, e.g. `docs/labels.yaml` for
PS 93/26, *Kjernekraft – naturvirkninger*. `label.py` reads the file line by line, so add no
other keys (a `case_no:` line would become a subtopic) and keep colons out of comments and
descriptions. Store it once with `python eval/label.py topics <agenda.yaml> <scheme.yaml>`,
then tag each passage with every subtopic that fits:
`add … --topic Arealbruk --topic "Vannmiljø og kjølevann"`. Unknown names are refused. The
report then shows recall per subtopic. The scheme is evaluation material: it must never be
copied into `context/` or a prompt.

### Rules for PS 93/26 (decided 28.10.2026)

- **Scope:** for PS 93/26 the brief covers only the natural effects of nuclear power. A
  passage is gold only if at least one subtopic fits. The competence programme, the
  county's role or emergency organisation without effects on nature or people are not gold.
- **Tag all that fit.** There is no primary tag.
- **Boundaries:**
  - The plant and its security zone → *Arealbruk*; power lines, roads etc. outside it →
    *Følgeinngrep*; a total footprint that includes both → both.
  - Anything about the waste itself, including leakage from storage or a repository →
    *Radioaktivt avfall*; add *Strålevern, utslipp og ulykker* only if the passage discusses
    radiation or consequences for nature or people.
  - Accident risk → *Strålevern, utslipp og ulykker* when the passage is about consequences
    for nature and people.
  - A comparison with another energy source → *Sammenligning med andre energikilder* plus
    the subtopic being compared (e.g. *Arealbruk*).
  - Noise from the plant or construction → *Landskap og friluftsliv*; ports built for the
    plant → *Følgeinngrep*.
- **Tags are used only on PS 93/26.** Passages for PS 94–98/26 are labelled without tags.
- This is a written rule for now; if annotators break it, a guard in `label.py` will be added.

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

## Status of `labels/fylkesutvalget_2026-09-29_A.yaml`

Annotator A's labels for the real meeting: PS 93/26 (40 passages, all tagged with the
subtopics in `docs/labels.yaml`) and PS 94–98/26 (43 passages, no tags; PS 97/26 from the case
paper plus cross-references into the planning provisions and impact assessment).

**Reminder:** `labels/fylkesutvalget_2026-09-29.yaml` is currently a **provisional** copy of
the A file (its `provenance` says so), made so the baseline could run before B exists. When B
is done: run `label.py agree`, merge, overwrite the gold file, set `reviewed_by`, and run
`eval-live` again. Results produced before that are A-only and must be reported as such. The passages were **drafted by the coding agent and confirmed
by annotator A** row by row (28.10.2026); the file says so in `labeller` and `provenance`.

- Annotator B labels independently into `labels/fylkesutvalget_2026-09-29_B.yaml` without
  opening the A file first.
- A reviewer compares A and B (`label.py agree`), resolves disagreements and writes the merged
  gold file `labels/fylkesutvalget_2026-09-29.yaml`, setting `reviewed_by`. Only that file is
  read by the harness, so the real meeting is not evaluated before the merge.
- `label.py` always writes to the unsuffixed path; rename the result to `_A`/`_B` when done.
- The A file is evaluation material: the coding agent must not use it when changing retrieval,
  prompts or any other pipeline stage.
- Report the agent drafting in the white paper: A-vs-B agreement is agent-assisted vs
  independent, not two independent annotators.
