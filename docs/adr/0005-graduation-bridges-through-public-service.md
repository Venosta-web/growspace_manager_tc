# Graduation bridges to Growspace Manager through its public service

Decided 2026-09-03 during the design grill for `growspace_manager_tc`.

The Graduation action optionally calls Growspace Manager's public Home
Assistant service to create the corresponding Plant (entering at
`clone → veg`) and stores the returned plant ID on the graduation record. If
the call fails or the user opts out, the action degrades to a manual marking —
the Culture still ends, the plant is simply created by hand in Growspace
Manager.

This keeps the same seam philosophy as ADR-0002: Growspace Manager's public
API is the only coupling between the two integrations, and it flows one way —
Growspace Manager never learns that TC exists. Closing this loop is what makes
TC useful: phenotype → preserved in culture → back into a grow run.
