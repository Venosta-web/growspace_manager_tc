# The TC ⇄ card WebSocket contract

This repository owns the `growspace_manager_tc/` WebSocket namespace. The
Lovelace card consumes it from a lazy chunk (ADR-0003), so a change here is one
feature across both repositories, backend side first:

```
TC handler → TC test → contract fixture → card zod schema → card chunk + test
```

The recorded payloads live in `tests/fixtures/contract/` and are fetched from
this repository's `main` by the card's contract-fixture workflow. They are
generated, never hand-edited:

```bash
../../.venv/bin/pytest tests/contract/ --regenerate-contract-fixture
pre-commit run prettier --all-files
```

The second line is not optional. Regeneration writes Python's JSON formatting,
which expands every array one element per line; prettier keeps short ones
inline, and the lint workflow's **Repository files** job fails on the
difference. The contract tests compare parsed payloads, so reformatting cannot
change what they assert — which is exactly why nothing but that job notices.

## Presence detection

Home Assistant gives a Lovelace card no way to ask whether a custom integration
is installed, so the card asks this namespace instead.

| the card sees     | what it means                                | what it does          |
| ----------------- | -------------------------------------------- | --------------------- |
| a result          | TC is installed and an entry is loaded       | render the TC surface |
| `unknown_command` | TC is not installed                          | render nothing        |
| `not_loaded`      | TC is installed, but its entry is not loaded | render nothing        |
| anything else     | unreachable, or a shape the card cannot read | render nothing        |

The namespace is registered from `async_setup_entry`, so it does not exist
before an entry loads. It is never unregistered — Home Assistant has no such
call — which is why `not_loaded` exists: a removed integration keeps answering,
and has to say so itself.

## `growspace_manager_tc/get_manifest`

Takes no parameters. Returns:

| field                 | type            | meaning                                          |
| --------------------- | --------------- | ------------------------------------------------ |
| `contract_version`    | int             | the shape of this namespace; `1` today           |
| `integration_version` | string          | the installed release, from `manifest.json`      |
| `features`            | string[]        | the features this installation can serve         |
| `collections`         | `{string: int}` | how many records each persisted collection holds |

`contract_version` and `features` are the two gates the card uses, and they
answer different questions. The version says which wire shape it reached; a
feature says a surface is actually there to call. Gate a surface on `features`,
never on `integration_version` — an installed release is not the claim that a
feature works.

`collections` carries a key for every collection this release knows about,
counting zero when nothing is stored in it — so the card can distinguish
"nothing set up yet" from "set up and empty" without fetching the records
themselves, and can tell both from a release that has never heard of the
collection at all. Keys appear as the V1 model tickets land.

## `growspace_manager_tc/culture_media/*`

The Culture Medium library. A medium is a named lineage; a **Medium Version** is
an immutable snapshot of its formulation, and every future Plating pins one
(ADR-0004). Gated by the `culture_media` feature.

| command                                     | parameters                       | result                        |
| ------------------------------------------- | -------------------------------- | ----------------------------- |
| `growspace_manager_tc/culture_media/list`   | —                                | `{ culture_media: Medium[] }` |
| `growspace_manager_tc/culture_media/create` | name + formulation               | `{ medium: Medium }`          |
| `growspace_manager_tc/culture_media/update` | `medium_id` + name + formulation | `{ medium: Medium }`          |
| `growspace_manager_tc/culture_media/delete` | `medium_id`                      | `{ medium_id: string }`       |

A `Medium` is `{ id, name, created_at, updated_at, current_version, versions }`.
`versions` is ordered oldest first and only ever grows; `current_version` names
the number a new Plating would pin, so the card never has to infer it from the
ordering. Each version is `{ version, created_at }` plus the formulation, flat:
`base_salts`, `additives[]`, `hormones[]`, `agar_g_per_l`, `sugar_g_per_l`,
`ph_target`, `notes`. An additive or hormone entry is
`{ name, amount, unit }` — the unit is free text, because hormones are dosed in
mg/L by some growers and µM by others.

The formulation travels flat on `create` and `update` too: one shape for the
form, the reply and the stored snapshot.

**`update` never rewrites a version.** It forks a new one when the formulation
changed, and leaves the history alone when it did not — so re-saving an
unchanged form adds nothing, and a rename adds nothing either. The name labels
the lineage; what a Plating pins is the formulation.

### Errors

Value rules live in the models, not in the voluptuous schemas, so that a value
the grower typed and a wrong type from the card do not arrive as the same error:

| code                | when                                                             |
| ------------------- | ---------------------------------------------------------------- |
| `validation_failed` | a value the grower has to fix; the message names the field       |
| `conflict`          | another medium already answers to that name (case-insensitively) |
| `entity_not_found`  | no medium with that `medium_id`                                  |
| `invalid_format`    | a wrong type on the wire — a card bug, from voluptuous           |
| `not_loaded`        | no config entry is loaded                                        |

The first three are spelled the way `growspace_manager` spells them, because
`hass-call.ts` narrows any code outside that set to `internal_error`.

## `growspace_manager_tc/culture_lines/*`

The culture board. A **Culture Line** is one preserved lineage of one
phenotype, started by a single **Introduction**; a **Culture** is one plantlet
group in one vessel. Gated by the `culture_lines` feature.

| command                                               | parameters                                  | result                      |
| ----------------------------------------------------- | ------------------------------------------- | --------------------------- |
| `growspace_manager_tc/culture_lines/list`             | —                                           | `{ culture_lines: Line[] }` |
| `growspace_manager_tc/culture_lines/introduce`        | phenotype + intervals + first-vessel fields | `{ line: Line }`            |
| `growspace_manager_tc/culture_lines/relink_phenotype` | `line_id` + phenotype                       | `{ line: Line }`            |
| `growspace_manager_tc/culture_lines/set_archived`     | `line_id` + `archived`                      | `{ line: Line }`            |

A `Line` is `{ id, phenotype, replate_interval_days, created_at, updated_at,
archived_at, cultures }`. `cultures` is always present — empty rather than
absent — so a line whose every Culture has ended reads the same shape as one
that never had any. `archived_at` is a stamp or `null` rather than a flag,
because when a line was put away is the question anyone asks about it.

`replate_interval_days` is `{ multiplication, rooting }`, in whole days. Both
stages are required: the number is the grower's protocol, and a defaulted one
would produce a Replate Due Date that looks authoritative and was invented.

A `Culture` is `{ id, line_id, stage, status, started_at, last_replated_at,
plantlet_count, location }`. `stage` is `multiplication` or `rooting` and is
what selects which interval applies. `status` is `active`, `discarded` or
`graduated`; an Introduction only ever produces `active`, and the other two are
written by the Maintenance Actions that own them — a Culture is never deleted.
`last_replated_at` is the anchor the interval is measured from, and an
Introduction sets it, because placing the explant _is_ a plating onto fresh
medium. `plantlet_count` is `null` when nobody counted, which is not the same
fact as a count of zero.

`introduce` takes `phenotype_id`, `phenotype_name`, `replate_interval_days`,
and optionally `stage`, `plantlet_count` and `location` for the first vessel.
It writes the line and that vessel together: a line with no Culture is a
lineage nobody is keeping alive.

### The phenotype reference, and the state the card owns

`phenotype` is `{ id, name_snapshot, snapshot_at }`. Growspace Manager owns
phenotype identity (ADR-0002), so **this namespace never resolves an ID** — it
stores an opaque string and the display name that string had when the reference
was taken. The card does the join client-side against Growspace Manager's
strain library.

That means **Missing Phenotype is the card's verdict, not a field on the
wire.** TC cannot know whether an ID still resolves, so no payload here says so
and no fixture can record it. What TC owns are the two ways out, and both are
commands: `relink_phenotype` points the line at another phenotype and takes a
fresh snapshot — the whole reference, never only the ID, so a line cannot
render under a name it no longer refers to — and `set_archived` puts the line
away. Neither deletes anything, and archiving is reversible on purpose:
archiving is what a grower reaches for when a reference goes missing, and a
one-way door there would make the honest move the frightening one.

A card that renders Missing Phenotype has to be sure the library it joined
against actually loaded. An empty strain library and a deleted phenotype look
identical from the join alone, and reporting every line as missing because a
fetch failed is a worse lie than showing a stale name.

### Ordering

`list` returns live lines before archived ones, then by the snapshotted
phenotype name, then by creation. Sorting on the snapshot rather than on the
resolved name is deliberate: an ordering computed here can only use what TC
holds, and it keeps a line whose phenotype was deleted in its place instead of
letting it jump when it goes missing. Archived lines are listed rather than
dropped — the card decides whether to show them, and a line that vanished from
the list would be indistinguishable from one that was deleted.

### Errors

The same vocabulary as the medium commands: `validation_failed` names the field
the grower has to fix, `entity_not_found` answers an unknown `line_id`,
`invalid_format` is voluptuous rejecting a wrong type from the card, and
`not_loaded` means no config entry is loaded.

## `growspace_manager_tc/maintenance/*`

The daily loop. A **Maintenance Action** is one recorded act on one Culture from
a closed vocabulary — Replate, Discard, note, move to rooting, Graduation — and
the history it writes is **append-only**: nothing in this namespace edits or
removes an act, because the Replate Due Date, the Plantlet Count series and the
Plating trail behind a Pairing are all derived from it. A mistake is corrected
by recording another act. Gated by the `maintenance` feature.

| command                                            | parameters                                    | result                   |
| -------------------------------------------------- | --------------------------------------------- | ------------------------ |
| `growspace_manager_tc/maintenance/replate`         | `culture_id`, medium pin, `vessels[]`, `note` | `{ line: Line, action }` |
| `growspace_manager_tc/maintenance/discard`         | `culture_id`, `reason`, `note`                | `{ line: Line, action }` |
| `growspace_manager_tc/maintenance/note`            | `culture_id`, `note`                          | `{ line: Line, action }` |
| `growspace_manager_tc/maintenance/move_to_rooting` | `culture_id`, `note`                          | `{ line: Line, action }` |
| `growspace_manager_tc/maintenance/graduate`        | `culture_id`, `note`                          | `{ line: Line, action }` |
| `growspace_manager_tc/maintenance/history`         | optional `culture_id` / `line_id`             | `{ actions: Action[] }`  |

**Five commands rather than one taking an action type.** The acts do genuinely
different things — one creates Cultures, two end one, one changes a Stage, one
only observes — so a single command would either take a union of every field or
validate none of them, and the card would have to know which combination belongs
to which act anyway. Five commands put that knowledge where voluptuous can check
it.

**Every act answers with the whole board entry for the line**, not with the
Culture it named: a Replate can divide one Culture into several, so the smallest
honest unit of change is the line. The recorded act travels back beside it, so
the card can show what it just wrote without re-reading the history.

An `Action` is flat, with every field always present:
`{ id, culture_id, line_id, action, recorded_at, note, medium_id,
medium_version, vessels, reason, stage }`. The fields an act does not use are
`null` or empty rather than absent — the card reads one schema, a persisted
record decodes without knowing which act it is first, and a reader counting
replates never has to guess whether a missing key means "not applicable" or "an
older release did not write it". `line_id` is denormalized on purpose: a line's
history has to stay readable after the vessels it happened in have ended.

`action` is one of `replate`, `discard`, `note`, `move_to_rooting`, `graduate`.
`reason` is one of `contamination`, `spent`, `mistake` — closed, because "how
much of this line was lost to contamination" is a question the record set has to
be able to answer; the note beside it carries whatever three words leave out.

### Replate, and the division

`replate` takes `medium_id` and `medium_version` — the Medium Version this
placement pins (ADR-0004) — and `vessels`, a list of at least one
`{ plantlet_count?, location? }`.

**The first vessel is the Culture that was replated**: its identity survives the
transfer, so its anchor and count move and its ID does not. Every further vessel
is a new Culture on the same line at the same Stage. A plain transfer and a
division are therefore the same command with a longer list: one dialog on the
card, one shape in the history, and a per-vessel multiplication rate that is a
subtraction rather than a reconstruction.

Two defaults are worth stating because collapsing them would lose information.
An **absent `location` inherits** the Culture's — a form that submits blank
fields would otherwise wipe every shelf label on the board — while an empty
string is the grower clearing it. An **absent `plantlet_count` leaves the count
unknown** rather than carrying the old one forward: after a division the
previous number describes something that no longer exists.

The reply's `vessels` name the Cultures the act produced, in the same order, so
the card can find the vessel it just created without diffing the board.

### The Replate Due Date

Every Culture in a `Line` payload carries `replate_due_at`: its
`last_replated_at` plus the interval its line defines for its current Culture
Stage. It is **derived and never persisted** — the interval lives on the line and
can be edited, so a stored copy would outlive the number that produced it.

It is `null` for a Culture that has ended: a discarded or graduated vessel is not
overdue, it is over. It is `null` too when the anchor cannot be parsed, because
a due date guessed from an unreadable stamp would be shown to the grower as a
fact.

**Overdue is the card's verdict, not a field.** TC states the date; whether it
has passed depends on the clock at the moment of rendering, and a boolean
computed when the payload was built would be stale the moment it sat in an atom.

`move_to_rooting` changes the due date without touching the anchor: the vessel is
still on the medium it was already on, and only the interval that applies to it
has changed. It is refused on a Culture already in rooting, so a count of stage
moves stays a count of stage moves.

### The calendar

One `calendar` entity per config entry carries the same due dates: one all-day
event per Culture awaiting a Replate, named from the Phenotype Reference's
snapshot — the only name this integration holds — and keyed by `uid` on the
Culture. Overdue vessels stay on it as events whose day has gone, which is why
V1 ships no overdue binary sensor: a second definition of overdue is one more
than the honesty budget allows (docs/v1-scope.md). Archived lines are left off;
a line put away is not work.

### Errors

The same vocabulary as everywhere in this namespace. `validation_failed` names
the value the grower has to fix — an empty note, a vessel list that is empty or
longer than 50, a reason outside the closed set, a Medium Version the medium
does not have, or an act on a Culture that has already ended. `entity_not_found`
answers an unknown `culture_id` or `medium_id`. `invalid_format` is voluptuous
rejecting a wrong type from the card, and `not_loaded` means no config entry is
loaded.

**Every act refuses on a Culture that has ended**, and refuses with
`validation_failed` rather than a not-found: the vessel exists, the board the
grower is looking at is merely stale.
