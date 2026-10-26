# Status — 24.10.2026

Executed against `project_plan.md` with `algorithms.pdf` as the test document (a synthetic
11-item agenda, `tests/cases/algorithms_synthetic/`) plus synthetic edge cases
(`tests/cases/edge_documents/`, `tests/cases/rejected_input/`).

## Built and tested

| Plan task | State | Evidence |
|---|---|---|
| T01–T03 repo, tooling, AGENTS.md | done | `pyproject.toml`, `Makefile` + `make.ps1`, `.pre-commit-config.yaml`, `AGENTS.md` |
| T06 S0 agenda schema + gate | done | `test_agenda.py` (closed/procedural/out-of-scope skipped, missing `closed` rejected, `saksbehandler` rejected) |
| T07 S1 fetch (allowlist, sha256 cache, local mode) | done | `test_fetch.py` |
| T08, T17, T19 S2 parse: pages, labels, segments, heading tree, invisible-text stripping, scanned-page flag | done | 336 pages → 4 412 segments, 209 headings, labels on 335/336 pages, 4 411/4 412 segments pass V1 against their own page |
| T18 tables | done, guarded | tables kept only if every row is verbatim on the page; the textbook has no ruled tables, so untested on real budgets |
| T20 S3 personal data | partly | ID number (checksum), e-mail, phone; person names by **rules** for case-paper blocks (header fields, signatures, letter closings, photo credits; `config/privacy.yaml`): 20 segments flagged in the 1 319-page Fylkesutvalget bundle, 0 in `algorithms.pdf`, one false positive (a reference list). **Names in running text are not detected** (no Norwegian NER model) |
| T11, T21 S4 index | partly | BM25 only; **dense multilingual embeddings not added** |
| T22 S5 cross-references | done (code only) | section / chapter / figure / table / page / exercise / appendix, nb + en patterns; no LLM fallback |
| T10, T27, T28 swappable LLM, record/replay | done | ollama, openai_compatible, anthropic adapters; per-stage model; `gdpr_approved` gate; replay is deterministic (identical numbers, 1 s vs 75 s) |
| T23 S6, T24 S7, T25 S8 | done | S7 adds section expansion; S8 has two strategies (`agent` tool loop ≤ 8 calls, `pointwise`) |
| T09, T26 S10 V1–V7 | done | `test_verify.py` |
| T13 S9 assemble JSON / Markdown / HTML | done | |
| T14, T38 CLI + inbox watcher | done | `briefer run`, `briefer watch [--once]`, `briefer purge` |
| T29 labelling guideline + helper | done | `docs/labelling_guideline.md`, `eval/label.py` (refuses non-verbatim quotes) |
| T32 synthetic cases | done | `tests/cases/make_synthetic.py` |
| T33, T34 harness, both agenda styles | done | `eval/harness.py`; candidate-recall diagnostic added |
| T35, T39, T40 web UI, languages, audit | done | `test_web.py`; smoke-tested on a real run |
| T36, T37 budget, kill switch 1–5 | done | `test_llm_safety.py` |
| T42 nightly CI | written, not run | `.github/workflows/ci.yml` (no remote configured) |

49 unit tests pass; `ruff` clean.

## Measured (live, 24.10.2026)

See `docs/stress_tests.md` §4.2 for the full table. Default configuration (qwen2.5:7b,
pointwise S8) on the algorithms agenda: recall 0.49 described / 0.40 titles-only, precision
0.20 / 0.18 (lower bound), retrieval ceiling 0.53 / 0.45, skips 3/3, rejects 2/2 and 1/2,
0 extracts failed V1–V5. Retrieval (S7) now limits recall more than selection does.

## Not done / needs people

- **Gold labels are provisional**, drafted by the coding agent before any run. Reviewing the
  first results shows they are too narrow (several "false positives" are relevant passages,
  e.g. the RSA summary box), so precision is a lower bound. T30 (two annotators, κ) is open.
- No **real Innlandet fylkeskommune meeting** yet (T04, T31): the plan's rule 5 requires one
  before the evaluation numbers mean anything for the actual use case.
- T41 large-agenda run on a real 200+ page budget, T43 demo, T44–T50, T51–T58 (white paper).
- gitleaks hook configured but not installed locally (no `pre-commit`/`gitleaks` on this PC).
- Targets in §3.4 are **not met** (recall ≥ 0.80 / 0.65, precision ≥ 0.60).
