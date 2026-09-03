# TC is a fourth sibling repo shipping an optional companion integration

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

Tissue-culture tracking must be installable and removable independently of
Growspace Manager, and the workspace already established the sibling-repo
pattern with `growspace_manager_vision`. We therefore created
`~/dev/growspace_manager_tc` as its own repository shipping the
`growspace_manager_tc` custom component, rather than a second domain inside
`growspace_manager` (not independently uninstallable) or a second component
inside the `growspace_manager` repo (one HACS repo maps to one integration in
practice).

## Consequences

- The hub (`growspace_manager_workspace`) map, scripts, and `AGENTS.md` gain a
  fourth product repo; hub tooling that assumes three repos must be extended
  deliberately, not accidentally.
- Cross-repo contract work (TC ↔ card) follows the existing rule: backend
  contract first, then integration client, then card.
