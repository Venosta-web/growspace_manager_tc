# Culture Medium versions are immutable

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

Every Plating pins a specific Medium Version, and editing a Culture Medium
creates a new version instead of rewriting the old one. Without this, "phenotype
X thrives on medium R" is a claim about a formulation that may no longer exist
as recorded, and any future derivation of pairing statistics from Plating
history computes against moving targets.

## Consequences

- "Derived stats later" (curated Pairings now, computed survival/multiplication
  later) stays possible without migration: the action log plus pinned versions
  is already sufficient evidence.
- The medium editor must present versions honestly (editing forks); hiding the
  version concept from the user was rejected for the same reason as mutability.
