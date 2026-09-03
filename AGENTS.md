# Agent instructions — growspace_manager_tc

## Session isolation

The main checkout is shared. Work on a branch in a repository-local worktree:

```bash
git fetch origin
git worktree add .worktrees/<branch-name> -b <branch-name> origin/main
```

Use `main` as the base until this repository documents another integration branch.
The pre-commit guard rejects commits made directly on `main`.

**Worktrees must live at `.worktrees/<name>`**, not anywhere else. The pre-commit
hooks resolve Python tools through `../../.venv/bin/...`, which reaches the
repository venv only from exactly that depth — from the main checkout it resolves
to `~/dev/.venv`, which does not exist, so every commit from the shared checkout
is rejected as a side effect of the path.

The workspace hub creates a matched TC + card pair for you with
`./scripts/feature new <name> --tc`.

## Test environment

One repository-local `.venv` (Python 3.14) lives in the main checkout and every
worktree shares it: `.venv/bin/pytest` from the main checkout,
`../../.venv/bin/pytest` from a worktree — the path the hooks already use.

**Never a Home Assistant core venv.** Its `syrupy` is newer than the one
`pytest-homeassistant-custom-component` pins, and every test dies at collection.

Build or refresh it two-phase, exactly as CI does — Home Assistant first, then
everything else under the constraints it ships. One unconstrained pass lets
transitive pins float past the pinned Home Assistant release:

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python "$(grep '^homeassistant==' requirements.txt)"
uv pip install --python .venv/bin/python -r requirements.txt -c "$(
  .venv/bin/python -c 'import homeassistant, pathlib; print(
    pathlib.Path(homeassistant.__file__).parent / "package_constraints.txt")'
)"
```

The venv is shared by every worktree, so refreshing it from one branch's pins is a
decision about all of them. The hub's guards re-check it before each run and name
the requirement that is unmet.

## Validation

```bash
../../.venv/bin/pytest tests/ -q          # from a worktree
pre-commit run --all-files                # repository files, ruff, mypy, pytest
```

From the workspace hub, `./scripts/check tc fast|full` runs the same suite and
prints which checkout it resolved; `GROWSPACE_TC=$PWD ./scripts/check tc` points
it at your worktree instead of the main checkout.

CI adds what a local run cannot: hassfest and HACS validation of `manifest.json`
and `hacs.json`, and Codecov upload.

## Cross-repository boundaries

Growspace Manager owns phenotype identity. Store its opaque phenotype ID plus a
display-name snapshot; keep missing references visible and repairable. Graduation may
call Growspace Manager only through its public service.

This integration does not run without Growspace Manager. The config flow aborts
when its domain is not loaded, and `async_setup_entry` raises
`ConfigEntryNotReady` if it disappears afterwards — an entry outlives the
integration that justified it. Both messages live in `strings.json`, and
`translations/en.json` is the copy Home Assistant actually serves: change one,
change both.

This repository owns the TC WebSocket contract. Land backend implementation, tests,
and contract fixtures before the Lovelace card schema, lazy TC chunk, and frontend
tests.
