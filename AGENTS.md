# Agent instructions — growspace_manager_tc

## Session isolation

The main checkout is shared. Work on a branch in a repository-local worktree:

```bash
git fetch origin
git worktree add .worktrees/<branch-name> -b <branch-name> origin/main
```

Use `main` as the base until this repository documents another integration branch.
The pre-commit guard rejects commits made directly on `main`.

## Validation

Run `pre-commit run --all-files` for the current documentation-only repository. The
`Tests` workflow also exercises the branch-maintenance safeguards. Once the Python
integration scaffold exists, that workflow automatically installs the Home Assistant
test environment, runs pytest with coverage, and uploads `coverage.xml` to Codecov.

The workspace hub does not yet create TC worktrees or expose `./scripts/check tc`.
Until that tooling lands, create worktrees and run validation from this repository.

## Cross-repository boundaries

Growspace Manager owns phenotype identity. Store its opaque phenotype ID plus a
display-name snapshot; keep missing references visible and repairable. Graduation may
call Growspace Manager only through its public service.

This repository owns the TC WebSocket contract. Land backend implementation, tests,
and contract fixtures before the Lovelace card schema, lazy TC chunk, and frontend
tests.
