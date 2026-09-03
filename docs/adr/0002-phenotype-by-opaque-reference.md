# TC references phenotypes by opaque ID and requires Growspace Manager

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

Phenotype identity (strains, phenotype names, image galleries) is owned by
Growspace Manager's strain library. TC stores only opaque phenotype IDs; the
card joins them client-side against Growspace Manager's WebSocket data. TC's
config flow refuses to complete when the `growspace_manager` domain is not
loaded, because phenotype linkage is a core feature, not a nice-to-have.

Rejected: TC reading Growspace Manager's `.storage/` files directly (welds the
two storage schemas together forever) and TC keeping its own synchronized
phenotype copy (two sources of truth for names).

## Consequences

- Renaming a phenotype in Growspace Manager is transparent (the ID survives);
  deleting one leaves a dangling reference in TC that must be surfaced, not
  silently dropped — handled as a design question in its own right.
- The TC ↔ Growspace Manager contract is exactly one sentence: "a phenotype ID
  is a stable string." No shared code, no shared schema.
