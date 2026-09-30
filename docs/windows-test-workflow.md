# Windows Test Workflow

Run these commands from the repository root in Windows PowerShell.

## Scope on Windows

Windows runs **focused checks only**. The full suite, models, Docker and
browser checks run on the Mac (`deproject-mac`), never on this laptop
(`CLAUDE.md`, `ROADMAP.md`). Do not install or launch WSL, Docker or VMs here.

## Interpreter

`python` on PATH may resolve to an Anaconda interpreter without `fastapi`.
Use the project interpreter explicitly:

```powershell
py -3.13 -m pytest tests/test_provider_settings.py -q -p no:schemathesis --basetemp=.tmp/pytest-focused
```

`-p no:schemathesis` disables the auto-loaded Schemathesis pytest plugin that
is broken on the current Windows development machine. `--basetemp=.tmp/pytest-…`
keeps pytest temp files inside the repository when the user temp root is not
readable. Use a distinct `--basetemp` per run so results are not confused.

## Lint

Pre-commit pins Ruff `v0.15.11` (`.pre-commit-config.yaml`). A locally
installed Ruff of another version can differ; report the version you ran:

```powershell
ruff --version
ruff check . --output-format concise
```

## Integration tests

Integration tests run on the Mac against PostgreSQL (see the
[E.5 capsule](evidence/e5-secret-scan.md)). On Windows run only the integration
module you changed, for example:

```powershell
py -3.13 -m pytest tests/integration/test_graph_lane_e2e.py -q -p no:schemathesis --basetemp=.tmp/pytest-integration
```

Some integration, browser, Docker, or external-tool tests skip when the
optional dependency or service is unavailable locally. A skip is not a pass:
run the corresponding check on the Mac before claiming completion.
