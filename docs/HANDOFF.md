# Handoff — Walking skeleton on the real meeting — 29.10.2026

Details: `docs/status.md` (task by task), `docs/stress_tests.md` (measurements and repairs),
`README.md` (setup and commands). `docs/section2_checklist.md` and `docs/report_checklist.md`
are the user's personal checklists for Compulsory 2: local only, never commit them (listed in
`.git/info/exclude`).

## Goal
Show the Agenda Brief Builder working end to end on a real Innlandet fylkeskommune meeting
(Fylkesutvalget 29.09.2026, PS 93–98/26) for Compulsory 2: real input, a normal run, an
evaluation against gold labels, and a repository a grader can clone and reproduce offline.

## Status
The walking skeleton runs end to end on the real meeting and both branches are pushed
(`main` = `2706d68`, `realagenda` = `2e1626a` at the time of the merge). Results are measured
against **provisional gold (annotator A only)**:

| style | recall micro / macro | precision | F1 | S7 ceiling |
|---|---|---|---|---|
| described | 0.10 / 0.21 | 0.08 | 0.09 | 0.10 |
| titles_only | 0.19 / 0.33 | 0.12 | 0.15 | 0.20 |

The §3.4 targets are **not met**. Retrieval (S7) is the bottleneck: the ceiling equals recall.

## Done so far
- Subtopic scheme for PS 93/26 rewritten as `docs/labels.yaml` (8 subtopics, boundary rules in
  `docs/labelling_guideline.md`); the PS 93/26 description names the theme, not the subtopics.
- Annotator A labels: `labels/fylkesutvalget_2026-09-29_A.yaml`, 83 passages (PS 93/26: 40
  tagged; PS 94–98/26: 43), drafted by the coding agent and confirmed row by row by the user.
  `labels/fylkesutvalget_2026-09-29.yaml` is a provisional copy (its `provenance` says so).
- `eval-live` on the real meeting (about 11 min for both styles, 227/232 LLM calls).
- `make run` defaults to the real meeting and stops with the download link if the PDF is
  missing; the synthetic agenda is an override (`-Agenda` / `AGENDA=`).
- Replay cache `data/llm_cache/` committed (0.4 MB, scanned for names); the harness reports a
  case with a missing source PDF as "not run". A fresh clone with `python -m venv` reproduces
  the live numbers offline.
- Prompt log: `docs/prompt_logs/2026-10-28-labelling-ps93.md`.
- Commits `6163dc9` (labelling), `babf734` (default run), `2e1626a` (replay cache), merge
  `2706d68` on `main`; this handoff and the `setup` change come in a later commit.

## In progress
- Checking that a fresh download of the møteinnkalling is byte-identical to ours (SHA-256
  `ecce772de86349ddaef2049400cac65cd8b776470386a4f0553792f881aa3ba5`). The meeting page loads
  the PDF through an internal API the agent may not call; the user downloads it by hand.

## Next steps
1. Compare the SHA-256 of a fresh browser download with ours; if it differs, note it in the
   README and decide how graders get the exact file.
2. Make the GitHub repo public before submission.
3. Annotator B labels independently (without opening the A file) into
   `labels/fylkesutvalget_2026-09-29_B.yaml`; then `label.py agree`, merge, overwrite the gold
   file, set `reviewed_by`, and run `eval-live` again (T30).
4. Bookmark scoping per item in S2/S7 (retrieval currently crosses items), then run again and
   report both.
5. Fix section paths mixing across items (the whole bundle's bookmark tree is read as one
   document, e.g. a PS 97 extract labelled with a PS 96 path).
6. Write the report (NeurIPS preprint, 3–4 pages, repo link) with the meeting reports and the
   prompt logs as appendices.
7. Confirm the §3.4 targets with the lecturer, or state in the report that they are unconfirmed.
8. Later, as before: T11 multilingual embeddings (ask before downloading a model), S8 strategy,
   person-name NER, cross-block hyphenation, T41–T58.

## Decisions and preferences
- Real-meeting numbers use A-only provisional gold for now; always report them as such. The
  agent must never draft the B file, and never use the labels when changing pipeline code.
- PS 93/26 brief covers only natural effects; tag every subtopic that fits; tags only on
  PS 93/26. PS 97/26 is labelled from the case paper plus cross-references into the planning
  provisions and impact assessment (`via: cross_reference`).
- The synthetic case (`tests/cases/algorithms_synthetic/`, its labels and cache entries) stays
  in the repository; only `algorithms.pdf` stays out.
- Always use `python -m venv`, never Anaconda/conda.
- Meeting reports and prompt logs are part of the report, written by the team.
- Ask before each task: questions, then a plan, then approval (user's CLAUDE.md).

## Key files
- `tests/cases/fylkesutvalget_2026-09-29/agenda.yaml`: the real agenda (items point to the whole bundle).
- `labels/fylkesutvalget_2026-09-29_A.yaml` / `labels/fylkesutvalget_2026-09-29.yaml`: A labels / provisional gold.
- `docs/labels.yaml`, `docs/labelling_guideline.md`: subtopic scheme and labelling rules.
- `eval/harness.py`, `eval/label.py`: evaluation and labelling tools.
- `data/llm_cache/`: committed replay cache.
- `make.ps1`, `Makefile`, `README.md`: commands and reproduction steps.

## Open questions / risks
- The municipality may regenerate the PDF; a different SHA-256 makes every replay lookup miss.
- Retrieval noise: table-of-contents lines, map legends, letter closings, bullet fragments.
- The name screen does not catch names in running text (one author name reached an eval report;
  `eval/runs/` is gitignored).
- The `Makefile` PDF check is tested only as a shell snippet (no `make` on the Windows PC).
- "described" scored lower than "titles_only" on this meeting, unlike the synthetic case.

## How to verify
```powershell
git switch main
.\make.ps1 test                                   # 55 passed
.\make.ps1 eval -Case fylkesutvalget_2026-09-29   # offline; recall 0.10 / 0.19 as above
.\make.ps1 run; .\make.ps1 ui                     # http://127.0.0.1:8000, 6 items awaiting review
```
`fylkesutvalget_2026-09-29.pdf` must be in the project root. Ollama (`llama3.2:3b`,
`qwen2.5:7b`) is needed only for `eval-live` and uncached runs.
