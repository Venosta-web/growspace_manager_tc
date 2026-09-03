# TC UI ships as a lazy chunk in the existing Lovelace card

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

The TC user interface is a new lazy-loaded chunk inside
`lovelace-growspace-manager-card` (following its existing code-splitting
pattern of ~16 lazy `growspace-[name]-[hash].js` chunks), rendered only when
the TC integration is detected. We rejected a separate card repository: it
would mean a second HACS install, a second Lovelace resource, and no shared
design system.

## Consequences

- The card repo now carries code for an integration that may be absent;
  detection of TC's presence (and graceful hiding when absent) is part of the
  card contract, not an afterthought.
- Users without TC download nothing eagerly — the chunk is only fetched when
  the TC surface is first shown.
