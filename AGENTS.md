# Instructions for the coding agent

You are helping build the Agenda Brief Builder (see `project_plan.md`). Read this first.

## Hard rules

- **Never read, open, list or modify anything under `labels/`** from pipeline code, and never
  read it to decide what the pipeline should return. Gold labels are for `eval/` only.
  `tests/unit/test_isolation.py` fails if `src/briefer` mentions that directory.
- The LLM never writes extract text. It returns segment IDs; code copies the text (§4.1).
  Do not add a code path that puts model output into `extracts[].text`.
- No names of people in agendas, logs, audit records or fixtures. Use roles
  (*fylkesordføreren*, "organiser").
- Closed items (`closed: true`) are never processed. Do not add defaults for `closed` or
  `in_scope`.
- Pipeline code reads `inbox/`, `data/raw/`, `context/`, `config/`; writes only `data/derived/`,
  `data/llm_cache/` and `runs/`. `data/raw/` is read-only after fetch.
- No secrets in code, prompts or logs. Keys come from the environment or `.env` (gitignored).

## Commands

| What | Windows | Linux/macOS |
|---|---|---|
| Unit tests | `.\make.ps1 test` | `make test` |
| Lint | `.\make.ps1 lint` | `make lint` |
| One run | `.\make.ps1 run` | `make run` |
| Evaluation (replay, offline) | `.\make.ps1 eval` | `make eval` |
| Evaluation (live model) | `.\make.ps1 eval-live` | `make eval-live` |
| Review UI | `.\make.ps1 ui` | `make ui` |

Run the unit tests after every change. Run `eval` (replay) before claiming a change does not
regress quality; run `eval-live` only when prompts, models or retrieval change.

## Conventions

- Python 3.11+, pydantic models in `models.py`, one module per stage (S0–S11) as in §11.
- Every stage logs to `run_log.jsonl` through `pipeline.RunLog`; add fields there rather than
  printing.
- New LLM calls go through `LLMClient.complete_json` with a JSON schema (with `maxLength` on
  free-text fields) so they are budgeted, cached and validated.
- Keep `docs/prompt_logs/` updated with excerpts of coding-agent sessions, including output
  that was corrected or rejected.
