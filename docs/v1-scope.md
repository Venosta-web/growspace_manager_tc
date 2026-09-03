# V1 Scope

Decided 2026-09-03 at the close of the design grill. Terms are as defined in
[CONTEXT.md](../CONTEXT.md); architecture in [docs/adr/](adr/).

## In V1 (backend)

- Culture Lines, Cultures, Culture Stages; Introduction as the line-creating act
- The five Maintenance Actions: Replate (with optional split), Discard, note,
  move to rooting, Graduation
- Culture Medium library with immutable Medium Versions; a Plating record per
  placement
- Curated Pairings (per-medium and per-phenotype are views of one record set)
- Replate Due Date: interval per Culture Stage defined on the Line, anchored to
  the Culture's last Replate
- One calendar entity per config entry; overdue state consumed by the card
- Graduation bridge through Growspace Manager's public service (ADR-0005)
- Plantlet Count on Cultures, recorded at Replate
- Optional free-text Location on Cultures

## In V1 (card, lazy chunk per ADR-0003)

- One TC view, landing on the due/overdue worklist
- Culture board: lines with their vessels, status, stage, ages
- Medium library with version history
- Pairing editor

## Explicitly out of V1

- **Derived pairing statistics** (survival/multiplication read-models) — they
  need months of recorded history; the data model (closed action set, pinned
  Medium Versions, Plantlet Counts) is designed so they can be added later
  without migration.
- **Import/export of TC data** — add once the storage shape has survived real
  use.
- **Overdue alert/binary_sensor entities** — calendar plus card only;
  automators trigger off the calendar entity. A second overdue definition is
  not worth v1 honesty cost.
- **Structured location hierarchy** — free text now; a contamination-by-shelf
  read-model can come later if it ever matters.
