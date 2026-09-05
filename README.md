# Growspace Manager TC

![Growspace Manager](custom_components/growspace_manager_tc/brand/logo.png)

[![Tests](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/tests.yaml/badge.svg)](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/tests.yaml)
[![HACS/HASS](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/validate.yaml/badge.svg)](https://github.com/Venosta-web/growspace_manager_tc/actions/workflows/validate.yaml)

The optional tissue-culture companion to
[Growspace Manager](https://github.com/Venosta-web/growspace_manager).
Preserve phenotypes in Culture Lines, follow the replate worklist, keep a
versioned Culture Medium library, curate pairings, and graduate Cultures back
into Growspace Manager plants.

## Requirements

- Home Assistant **2026.8.1 or newer** and HACS **2.0.5 or newer**.
- **Growspace Manager installed, configured, and loaded** in the same Home
  Assistant instance. TC references the phenotypes in its strain library;
  Growspace Manager owns their identity. TC cannot run on its own.
- The [Growspace Manager card](https://github.com/Venosta-web/lovelace-growspace-manager-card)
  with the TC view, including the graduation bridge from workspace issue #118.
  During the V1 rollout this may require enabling prereleases in HACS.
  The integration does not install the card automatically.

## Install through HACS

1. Install and configure Growspace Manager first. Add a phenotype to its
   strain library and a growspace with an empty position for graduation.
2. In HACS, open the three-dot menu, then **Custom repositories**. Add
   `https://github.com/Venosta-web/growspace_manager_tc` with type **Integration**.
3. Find **Growspace Manager TC**, download it, and restart Home Assistant.
   Before the first GitHub release is published, HACS offers the `main` branch.
   After publication, select the release whose changes you want from the
   [changelog](CHANGELOG.md).
4. Open **Settings → Devices & services → Add integration**, search for
   **Growspace Manager TC**, and complete setup. Only one TC entry is supported.
5. Install or update the Growspace Manager card through HACS, add it to a
   dashboard, then open its **TC** view. TC appears when its integration is loaded.

No YAML configuration, separate dashboard card, or cloud account is required
for TC. HACS uses GitHub for installation and updates; TC runs locally.

To update, download the desired version in HACS and restart Home Assistant.
Keep Growspace Manager and the card compatible with the TC version in use.

## Your first culture loop

1. **Introduce a line.** Select a phenotype from Growspace Manager, choose
   multiplication or rooting, and set the replate interval for each stage.
   Optionally record the Plantlet Count and a free-text Location. Introduction
   creates the line and its first Culture.
2. **Prepare a Culture Medium.** In the medium library, name the formulation
   and record its base salts, additives, hormones, agar, sugar, and target pH.
   Changing a formulation creates an immutable Medium Version.
3. **Work from the worklist.** The TC view opens on due and overdue replating.
   Replate a Culture onto a selected Medium Version, recording Plantlet Counts
   and Locations for the resulting vessels. One vessel continues the Culture;
   additional vessels create new Cultures in the same line.
4. **Record maintenance.** Add notes, move a Culture to rooting, or discard it
   with a reason. Ended Cultures and their action history remain available.
   Replating resets the due-date anchor; moving to rooting applies the rooting
   interval to the existing anchor. Until the first Replate, Introduction is
   the anchor.
5. **Curate pairings.** Endorse a phenotype–Culture Medium combination with
   notes. The phenotype and medium views show the same pairing set. A Pairing
   endorses the medium across versions; each Replate pins the version used.
6. **Graduate.** End a Culture and optionally create a plant in Growspace
   Manager by selecting its destination and genetics. The plant enters as a
   clone for later vegetative growth, and the graduation record links its ID.
   Opting out or a failed bridge still saves the graduation. If the plant link
   is missing, inspect Growspace Manager before adding a plant manually: a
   remote call can fail after creating one, so TC does not retry it.

## Calendar, history, and recovery

TC creates one calendar entity per integration entry for replate due dates.
Use it in Home Assistant calendars and automations. Overdue work is shown in
that calendar and the card; there are no separate overdue alert entities.

A removed phenotype stays visible under its saved name. Re-link the Culture
Line to an existing phenotype or archive it. TC never deletes a line because
its phenotype is missing.

TC stores its records locally in Home Assistant's `.storage` directory.
Include the configuration directory in your normal Home Assistant backups;
do not edit the store while Home Assistant is running.

If setup says Growspace Manager is missing, check that its integration is
loaded, not merely downloaded in HACS. If it becomes unavailable after TC has
been configured, TC waits for it to return. If TC is absent from the card,
check the integration's setup state, update the card, and reload the dashboard.

## V1 boundaries

V1 includes Culture Lines and Cultures, five Maintenance Actions, stage-based
replate dates, one calendar, Plantlet Counts, free-text Locations, immutable
Medium Versions, curated Pairings, and optional graduation into a plant.

Derived statistics, TC import/export, overdue alert or binary-sensor entities,
and structured location hierarchies are outside V1. See the
[scope](docs/v1-scope.md), [WebSocket contract](docs/websocket-contract.md), and
[release verification](docs/release-readiness.md).

## Development and branding

See [AGENTS.md](AGENTS.md) for the isolated worktree and validation commands,
[CONTEXT.md](CONTEXT.md) for terminology, and [ADRs](docs/adr/) for design decisions.
TC ships the shared Growspace Manager brand assets under its own `brand/`
directory. These are reused unchanged from the sibling integration under this
project's GPL-3.0 license. Home Assistant serves these local assets without a
separate submission to the Home Assistant brands repository.
