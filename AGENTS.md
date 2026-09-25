# Agent instructions — growspace_manager_tc

## Session isolation

The main checkout is shared. Work on a branch in a repository-local worktree,
based on the channel the change belongs to (see **Base branch** below):

```bash
git fetch origin
git worktree add .worktrees/<branch-name> -b <branch-name> origin/<base>
```

**Worktrees must live at `.worktrees/<name>`**. The Python pre-commit hooks
resolve tools from the worktree's own `.venv` first, then the main checkout's
`.venv` via `git rev-parse --git-common-dir`. The `no-commit-to-branch` hook
protects `main` in the shared checkout.

The workspace hub creates a matched TC + card pair for you with
`./scripts/feature new <name> --tc`.

### Base branch

Two branches publish, so which one you branch from is a release decision:

- **`main`** is the stable channel. A push publishes `vX.Y.Z` from
  `custom_components/growspace_manager_tc/manifest.json` and HACS offers it to
  everyone. Base ordinary feature and fix work here.
- **`prerelease`** is the beta channel. A push publishes
  `vX.Y.(Z+1)b<run>` — a beta of the _next_ patch — which HACS offers only with
  `show_beta` enabled, and prunes to the newest five. Integrate work here when
  it wants exercising by a tester before it reaches every install: architecture
  and refactor changes, and anything whose blast radius is wider than its diff.

Both are protected and reject commits made directly on them; the pre-commit
guard rejects a commit on `main` locally as well. The manifest on `prerelease`
keeps naming the _stable_ version it is a beta of — the prerelease workflow
writes the computed version into its workspace copy and never commits it,
because that stable number is what the next run's calculation reads.

## Test environment

The Python pre-commit hooks run through `.github/scripts/run_venv_tool.py`.
They use `<worktree>/.venv/bin/<tool>` when present (including a symlink), then
the main checkout's `.venv/bin/<tool>`. If neither has pytest or mypy, the hook
fails and names both paths. A worktree with no `.venv`, or one linked to the main
venv, keeps using the main environment. A branch that changes dependency pins
can instead use a private `.venv` built from its own `requirements.txt`; this
keeps its hooks independent of other worktrees. See hub ADR 0004, "Python hooks
run the worktree's own venv".

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
.venv/bin/pytest tests/ -q               # with a private or linked worktree .venv
../../.venv/bin/pytest tests/ -q          # from a worktree with no .venv
pre-commit run --all-files                # repository files, ruff, mypy, pytest
```

From the workspace hub, `./scripts/check tc fast|full` runs the same suite and
prints which checkout it resolved; `GROWSPACE_TC=$PWD ./scripts/check tc` points
it at your worktree instead of the main checkout.

CI adds what a local run cannot: hassfest and HACS validation of `manifest.json`
and `hacs.json`, and Codecov upload.

## Dependency updates

Dependabot reads `.github/dependabot.yml` from the default branch and opens
weekly Monday pull requests against `prerelease` for GitHub Actions and pip
dependencies. Dev tools are grouped. `requirements.txt` is the single pin source
for Ruff, mypy, and yamllint: the lint workflow installs its tools from that file
and checks the Ruff and yamllint pre-commit revisions against it. Codespell is
intentionally unpinned in the local environment; its pre-commit revision owns
the version used by the repository check.

Home Assistant and `pytest-homeassistant-custom-component` arrive as one
`home-assistant-test-stack` PR. The plugin pins an exact Home Assistant version;
the Tests workflow checks that published plugin pin against `requirements.txt`
before resolving the rest of the environment. If the plugin lags a new Home
Assistant release, leave the PR unmerged until a plugin release supports it,
then update both pins together. Check that the new HA release still supports
our Python version and that the manifest's minimum Home Assistant version is
appropriate before merging. The pytest stack is excluded from individual
Dependabot updates because the plugin pins it; HA-constrained transitive
packages are governed by `homeassistant/package_constraints.txt` and are not
restated in `requirements.txt`.

Dependabot pull requests run the same required checks as other pull requests.
Inspect the full status rollup, including `codecov/patch`, before merging one.

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
