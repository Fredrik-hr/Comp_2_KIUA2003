# Handoff — 26.10.2026

Read this first when picking the work up again. Details: `docs/status.md` (task by task),
`docs/stress_tests.md` (measurements and repairs), `README.md` (setup and commands).
`docs/section2_checklist.md` and `docs/report_checklist.md` are the user's personal
checklists for Compulsory 2: local only, never commit them (listed in `.git/info/exclude`).

## Where we are

- Work is on branch **`realagenda`** (commit `4e07228`), **not pushed**. `main` is pushed and
  matches `origin/main`. This file is not committed yet.
- **First real meeting added (T04):** Fylkesutvalget, Innlandet fylkeskommune, 29.09.2026,
  items PS 93–98/26, all open and in scope. Agenda: `tests/cases/fylkesutvalget_2026-09-29/`.
  The input is one 1 319-page møteinnkalling (case papers + all attachments, with PDF
  bookmarks per item), saved as `fylkesutvalget_2026-09-29.pdf` in the project root (not
  committed). Source:
  <https://prod01.elementscloud.no/publikum/920717152/DmbMeeting/1544> (in the README).
- Every item points to the **whole bundle** (baseline). Bookmark-based scoping per item is
  planned after the baseline, to measure the difference.
- **The pipeline has not been run on the real meeting.** It waits for labels (label before
  output). The harness now skips any case without a labels file and reports it as "not run".
- **S3 name screen (rules, not NER):** header fields, signatures, letter closings, photo
  credits (`config/privacy.yaml`). On the bundle: 20 segments flagged, 1 false positive (a
  reference list), 0 in `algorithms.pdf`. Names in running text are still not detected.
- **Subtopic labels:** `docs/labels.yaml` is the team's scheme for PS 93/26
  (*Kjernekraft – naturvirkninger*, 8 subtopics). `eval/label.py topics` stores it,
  `add --topic` tags passages, and the report shows recall per subtopic.
- Results on the synthetic case are unchanged: recall 0.49 / 0.40, precision 0.20 / 0.18.
  The §3.4 targets are **not met**.
- 53 unit tests pass, `ruff` is clean, `.\make.ps1 eval` (replay) reproduces the numbers.

## What I am not fully comfortable with

1. **The descriptions in the real agenda are mine.** `description` and `recommendation` were
   drafted by the coding agent from the case papers (marked in the file header). A team
   member should check them before the run.
2. **The subtopic scheme must stay out of the pipeline.** If it reaches `context/` or a
   prompt, the evaluation measures our checklist instead of retrieval.
3. **The harness ran the real meeting once before labels existed** (replay, 0 model calls,
   no selections). Nobody looked at the output and the run was deleted; the harness is fixed.
   Worth a line in the prompt logs.
4. **Reproducibility is weaker than the README says.** The replay cache (`data/llm_cache/`)
   is gitignored, so `make eval` on a fresh clone needs Ollama with both models. `make run`
   still uses the textbook, which others must get themselves.
5. **No prompt logs or meeting reports exist yet.** Both are required appendices.

## What's next (in order)

> **Reminder (added 28.10.2026):** the real meeting is labelled by annotator A only
> (`labels/fylkesutvalget_2026-09-29_A.yaml`, 83 passages, agent-drafted and human-confirmed),
> and `labels/fylkesutvalget_2026-09-29.yaml` is a **provisional** copy of it so the baseline
> could run. Annotator B must still label independently, then `label.py agree`, merge,
> overwrite the gold file, set `reviewed_by`, and re-run `eval-live`. Step 2 below is open.

1. **Commit** this handoff; **push** `realagenda` (or merge to `main`) after the team has
   looked at it.
2. **Label the real meeting** (people, not the agent): both team members, independently,
   following `docs/labelling_guideline.md`; store the scheme first with
   `python eval/label.py topics tests/cases/fylkesutvalget_2026-09-29/agenda.yaml docs/labels.yaml`.
   Then run the agreement step (T30).
3. **Run the baseline** on the real meeting (whole bundle), then add **bookmark scoping** per
   item in S2/S7 and run again; report both.
4. **Fix reproducibility:** commit the replay cache or correct the README; make the real
   meeting the default `make run`.
5. **Compulsory 2 report:** follow the user's local `docs/report_checklist.md`; write prompt logs and meeting
   reports; confirm the deadline and the §3.4 targets with the lecturer.
6. **Then, as before:** improve retrieval (T11, multilingual embeddings: ask before
   downloading a model), decide the S8 strategy, person-name NER, gitleaks + CI, cross-block
   hyphenation, later milestones T41–T58.

## How to resume quickly

```powershell
git switch realagenda
.\make.ps1 test        # should say 53 passed
.\make.ps1 eval        # replay; reproduces the numbers above; real meeting "not run" until labelled
.\make.ps1 run         # one run on the real meeting (needs the PDF); then .\make.ps1 ui → http://127.0.0.1:8000
```

Ollama must be running with `llama3.2:3b` and `qwen2.5:7b`; `algorithms.pdf` and
`fylkesutvalget_2026-09-29.pdf` must be in the project root.
