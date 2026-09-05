# Changelog

## 1.0.0 — V1

The version in `custom_components/growspace_manager_tc/manifest.json`, the one
the card reads back from `get_manifest`, and the one `v1.0.0` publishes: a push
to `main` cuts the tag from the manifest and attaches
`growspace_manager_tc.zip`, which `hacs.json` points HACS at instead of this
repository's default branch. The archive carries the integration runtime only —
no `tests/`, no `docs/`, no repository scaffolding.

- Introduce Culture Lines from Growspace Manager phenotype references, with
  display-name snapshots, re-linking, and archiving.
- Track Cultures through multiplication and rooting, Plantlet Counts, and
  optional free-text Locations.
- Record Replate (including splits), Discard, notes, moves to rooting, and
  Graduation in persistent, append-only action history.
- Compute stage-based Replate Due Dates and expose one calendar per TC entry.
- Manage Culture Medium formulations with immutable Medium Versions and
  pinned Platings, plus curated phenotype–medium Pairings.
- Optionally graduate through Growspace Manager's public `add_plant` service,
  retaining the graduation even when plant creation fails or is declined.
- Ship the shared brand assets under `brand/`, which Home Assistant serves
  itself, and document HACS installation, the Growspace Manager requirement,
  the V1 surface, recovery, and how the release was verified.

Derived statistics, import/export, and overdue alert entities are not included;
see [V1 boundaries](docs/v1-scope.md).

## 0.1.0 — Initial development

Integration scaffold, Growspace Manager setup guard, persistence, and the TC
WebSocket namespace. V1 capabilities were developed incrementally on `main`.
