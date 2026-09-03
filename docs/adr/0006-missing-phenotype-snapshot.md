# Missing phenotype references: name snapshot and an explicit state

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

ADR-0002 made phenotype references opaque IDs owned by Growspace Manager, so a
phenotype deleted there dangles here. TC stores a display-name snapshot at
reference time, renders a Missing Phenotype state from that snapshot when the
ID no longer resolves, and lets the user re-link or archive the affected
Culture Lines — references are never silently dropped.

The snapshot looks like it contradicts ADR-0002's "no phenotype copy"; it does
not. The ID remains the only authority for identity and joins; the snapshot is
a display fallback, not data ownership. Cross-integration cleanup — Growspace
Manager's delete notifying TC — was rejected because it would teach Growspace
Manager that TC exists, inverting the dependency direction the whole design
depends on.
