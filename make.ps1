# Windows equivalent of the Makefile:  .\make.ps1 test | run | eval | eval-live | ui | watch | purge
param([string]$Target = "test", [string]$Case = "", [string]$Agenda = "tests/cases/algorithms_synthetic/agenda.yaml")
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
$env:PYTHONIOENCODING = "utf-8"
$caseArgs = @(); if ($Case) { $caseArgs = @("--case", $Case) }
switch ($Target) {
    "setup"     { python -m venv .venv; & $py -m pip install -e ".[dev]" }
    "test"      { & $py -m pytest -q }
    "lint"      { & $py -m ruff check src eval tests }
    "run"       { & $py -m briefer run $Agenda }
    "eval"      { & $py eval/harness.py @caseArgs }
    "eval-live" { & $py eval/harness.py --live @caseArgs }
    "ui"        { & $py -m briefer ui }
    "watch"     { & $py -m briefer watch }
    "purge"     { & $py -m briefer purge }
    "synthetic" { & $py tests/cases/make_synthetic.py }
    default     { Write-Error "unknown target $Target" }
}
