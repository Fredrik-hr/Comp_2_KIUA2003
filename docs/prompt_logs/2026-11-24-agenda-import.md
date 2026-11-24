# 2026-11-24 — Agenda import from an uploaded møteinnkalling

**Request:** "Could we make a script that turns the agenda uploaded to the website to be
'translated' into a .yaml file?" Ten clarifying questions came first; the team accepted all
the defaults: PDF and .docx, both web UI and CLI, code only (no LLM), suggest values but never
default `closed`/`in_scope`, write to `inbox/`, flag names.

**Agent output (trimmed):** `src/briefer/agenda_import.py` (header fields, saksliste regex
`PS|RS|OS|DS|FO nn/yy`, type from the prefix, closed hint from the "UOFF (Lukket)" column),
an upload → review form flow, `briefer convert`, and tests that include the real Fylkesutvalget
PDF.

**Kept / corrected / rejected:**
- Kept: the draft cannot be saved until a person sets `closed` and `in_scope` on every item;
  the CLI draft keeps them `null`, so S0 rejects it until it is completed.
- Corrected by the agent after inspecting the real PDF: case number and title are on separate
  lines and titles wrap, so the parser joins continuation lines until a blank line; the
  case papers repeat the number without the prefix, so items come from the first run of pages
  that list cases only.
- Corrected: every item shared one attachment dict, which PyYAML wrote as `&id001` aliases;
  each item now gets a copy.
- Deferred: LLM drafting of `description` / `recommendation`; adding rows in the review form;
  `briefer purge` does not clean `data/raw/uploads/` yet.

**Corrected by the team — wrong branch:** the agent built the web part on `main`, whose UI was
the old one; the agreed design (Claude Design mock-up, commit `da50b86`) lived on the unmerged
`design` branch. The team asked to move the work there. The converter, CLI and tests were
carried over unchanged; the web part was rewritten into the design: the design's upload box
also accepts `.pdf`/`.docx`, the draft form is a new view of the design's `upload.html`, and a
confirmed draft goes to `inbox/pending/` and the design's existing preview and *Start* step
instead of straight to `inbox/`. Lesson: check `git branch -a` for unmerged work before
building UI.

## Same session — "why", need-to-know categories, orientation view, meeting PDF

**Requests (in order):** show information "in smaller context windows" to help someone get
oriented before the meeting; add a "why" for each extract; "it is supposed to find the
information a person would need to know to be able to partake in the meeting"; combine the
extracts into one file the meeting organiser can share.

**Agent output (trimmed):** first found that the 13.10 run had empty briefs because the S8
model (`qwen2.5:7b`) was not pulled (Ollama 404), not because of code. Then proposed six
need-to-know categories (decision, background, consequences, assessment, input, other) as
the organising idea for all three requests, and a three-phase plan.

**Kept / corrected / rejected:**
- Kept: no model-written summaries; the orientation view shows the start of verbatim extracts
  cut at a sentence boundary; the model note stays labelled as machine-written.
- Kept: the proposed decision (innstilling) is found by code (`innstilling.py`), not by the
  model — found for all 10 items in the two real bundles.
- Team decisions on the shared file: PDF only; only approved items, export disabled until
  every processed item is approved or rejected; rejected items listed as "ingen brief";
  closed items shown with case number and "lukket sak" only, never the title.
- Stopped mid-work for approval: `context/output_schema.json` (V6) had to accept the new
  optional extract fields; it was not in the approved plan.
- Rejected by the agent: a model-written "questions to ask" category (would be model text in
  the brief).
