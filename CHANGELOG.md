# Changelog

## 1.0.0 — V1 release candidate

Prepared for the first V1 release; this entry does not imply a published tag.

- Introduce Culture Lines from Growspace Manager phenotype references, with
  display-name snapshots, re-linking, and archiving.
- Track Cultures through multiplication and rooting, Plantlet Counts, and
  optional free-text Locations.
- Record Replate (including splits), Discard, notes, moves to rooting, and
  Graduation in persistent action history.
- Compute stage-based replate dates and expose one calendar per TC entry.
- Manage Culture Medium formulations with immutable Medium Versions and
  pinned Platings, plus curated phenotype–medium Pairings.
- Optionally graduate through Growspace Manager's public `add_plant` service,
  retaining the graduation even when plant creation fails or is declined.
- Document HACS installation, the Growspace Manager requirement, the card's V1
  workflow, recovery, and release verification; bundle the shared brand assets.

Derived statistics, import/export, and overdue alert entities are not included.

## 0.1.0 — Initial development

Integration scaffold, Growspace Manager setup guard, persistence, and the TC
WebSocket namespace. V1 capabilities were developed incrementally on `main`.
