# Windows equivalent of the Makefile:  .\make.ps1 test | run | eval | eval-live | ui | watch | purge
param([string]$Target = "test", [string]$Case = "", [string]$Agenda = "tests/cases/fylkesutvalget_2026-09-29/agenda.yaml")
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
$env:PYTHONIOENCODING = "utf-8"
$caseArgs = @(); if ($Case) { $caseArgs = @("--case", $Case) }
switch ($Target) {
    "setup"     {
        $base = if ($env:PYTHON) { $env:PYTHON } else { "python" }   # any Python 3.11+, not conda
        & $base -m venv .venv; & $py -m pip install -e ".[dev]"
    }
    "test"      { & $py -m pytest -q }
    "lint"      { & $py -m ruff check src eval tests }
    "run"       {
        if ($Agenda -like "*fylkesutvalget_2026-09-29*" -and -not (Test-Path (Join-Path $PSScriptRoot "fylkesutvalget_2026-09-29.pdf"))) {
            Write-Error "fylkesutvalget_2026-09-29.pdf is missing in the project root. Download it from https://prod01.elementscloud.no/publikum/920717152/DmbMeeting/1544 (see README)."; exit 1
        }
        & $py -m briefer run $Agenda
    }
    "eval"      { & $py eval/harness.py @caseArgs }
    "eval-live" { & $py eval/harness.py --live @caseArgs }
    "ui"        { & $py -m briefer ui }
    "watch"     { & $py -m briefer watch }
    "purge"     { & $py -m briefer purge }
    "synthetic" { & $py tests/cases/make_synthetic.py }
    default     { Write-Error "unknown target $Target" }
}
