# V1 release verification

Workspace issue
[#119](https://github.com/Venosta-web/growspace_manager_workspace/issues/119)
asks for the one thing no test suite in this repository can answer: that a
grower who has never seen it can install it from HACS and carry a Culture from
introduction through to a plant. This is the record of that run, and how to
repeat it.

## Where it runs, and why not the dev instance

The workspace hub's `ha-test` instance at `http://localhost:8124` mounts one
thing — its own configuration directory. No integration source and no card
build is bind-mounted into it, so everything under `custom_components/` and
`www/community/` got there by HACS downloading it from GitHub. That is the
whole point: the dev instance at :8123 mounts the working tree, so it would
pass happily on files HACS never delivers.

The instance keeps HACS and one onboarded owner between runs and nothing else —
no Growspace Manager, no TC, no records — so that HACS's GitHub authentication
survives without any development state coming with it. Its passwordless
trusted-network login is hub test configuration, not a TC installation step.

## The run of 2026-09-05

Home Assistant 2026.8.2, HACS 2.0.5.

| downloaded through HACS                       | category    | ref                                 |
| --------------------------------------------- | ----------- | ----------------------------------- |
| `Venosta-web/growspace_manager`               | Integration | `v1.2.3b428` (prereleases on)       |
| `Venosta-web/growspace_manager_tc`            | Integration | `codex/issue-119-release-readiness` |
| `Venosta-web/lovelace-growspace-manager-card` | Dashboard   | `v1.3.0-next.59` (prereleases on)   |

TC has no published release, so HACS listed branches and downloaded the branch
archive — the same path a user takes today, where HACS offers `main`. The card
arrived as 36 files in `www/community/lovelace-growspace-manager-card/`, one
release's complete asset set, and registered its own Lovelace resource; nothing
was hand-added to `configuration.yaml`.

### What the instance showed

- **The integration set up and stayed up.** One config entry, `loaded`.
- **Exactly one entity**, `calendar.growspace_manager_tc_replates`. The entity
  registry holds no other row for the platform, which is the V1 scope claim
  stated as a fact rather than an intention: no derived statistics, no
  import/export, no overdue alert or binary sensor.
- **`get_manifest` answered** `contract_version: 1`,
  `integration_version: 1.0.0`, and the five features
  `culture_media`, `culture_lines`, `maintenance`, `pairings`,
  `graduation_bridge`.
- **The brand images are served locally.** `/api/brands/integration/`
  `growspace_manager_tc/{icon,logo,dark_icon,dark_logo,icon@2x}.png` all
  answered `200 image/png` out of the HACS-installed `brand/` directory, with
  no CDN entry and no `home-assistant/brands` submission.
- **The whole loop was worked**, through the card and the WebSocket namespace:
  a line introduced from a Growspace Manager phenotype; a medium created and
  then edited into a second, immutable Version; a Replate splitting one Culture
  into five vessels with their own Plantlet Counts and Locations, pinning
  Version 1; a note; a move to rooting; a Discard with a reason; a Pairing
  created, edited and read back through both projections.
- **Graduation was exercised on all three paths.** Declined, the ending is
  recorded plain. Pointed at a growspace that does not exist, `add_plant`
  failed, the failure was logged, and the ending survived it. Given a real
  growspace and a free position, the plant was created and its ID stored on the
  graduation record — `21f7ad74-…`, present in Growspace Manager's own store at
  row 1, column 1, stage `clone`, and visible on its card.
- **The calendar followed.** After that graduation it dropped the graduated
  vessel and kept the one remaining live Culture's due date, carrying its
  stage, Location and last-Replate anchor in the event.
- **The card rendered the full V1 surface** from the HACS-installed bundle:
  the due/overdue worklist with its Location filter, the culture board with the
  line's five vessels and its two stage intervals, the medium library showing
  Version 2 with its history, and the pairing editor in both groupings.

### What this run does not prove

- **The refusal without Growspace Manager.** Growspace Manager was installed
  first here, so the config flow's abort and `async_setup_entry`'s
  `ConfigEntryNotReady` were not re-exercised against the live instance; they
  are covered by this repository's tests.
- **A HACS _update_.** There is only one ref to install, so install-then-update
  was not walked. That path is worth its own attention rather than an
  assumption: HACS does not clean the directory it downloads into, and on the
  card side that produced a live install serving one release's entry file on
  another release's chunk set. An integration is a whole directory rather than
  single-file content, so it is not the same failure — but the first TC release
  after this one is the moment to check it, the way
  `scripts/card-hacs-update` in the hub checks the card.
- **That the TC card appears at all on an idle dashboard.** The card hides
  itself until its `get_manifest` probe answers, and Home Assistant's
  `hui-card` re-reads that hidden flag only when `hass` or the card config
  changes. On this quiet test instance the card stayed collapsed after a
  reload until the next state update, then appeared complete. On an instance
  with entities that actually change this is invisible. It is card-side
  behaviour rather than TC's, filed as
  [workspace #146](https://github.com/Venosta-web/growspace_manager_workspace/issues/146),
  and recorded here because it is what the acceptance run saw.

## Reproducing it

1. From the main hub checkout, `./scripts/ha test up`. On a fresh instance,
   finish Home Assistant onboarding and add HACS. Use `ha-test` only — never
   the dev instance, whose read-only `dist/` mount a HACS download would be
   writing through.
2. Add Growspace Manager and TC as HACS custom repositories of category
   Integration, and the card as category Dashboard. Turn prereleases on for
   Growspace Manager and the card. Growspace Manager's `zip_release` packaging
   needs a published release rather than a branch.
3. Restart. Add TC **before** configuring Growspace Manager if you want to see
   the refusal; then configure Growspace Manager, give it a phenotype and a
   growspace with a free position, and add TC.
4. Add a dashboard with `custom:growspace-manager-card` and
   `custom:growspace-tc-card`, and work the loop in the
   [README](../README.md#your-first-culture-loop) end to end.
5. Check the three V1 boundaries as facts, not intentions: one entity in the
   registry for the platform, no import/export or statistics command in the
   namespace `get_manifest` reports, and nothing overdue outside the calendar
   and the card.
6. Run the suite against the tree you are releasing, from the main hub:

   ```bash
   GROWSPACE_TC=/path/to/growspace_manager_tc/.worktrees/<name> \
     ./scripts/check tc full
   ```

   and `pre-commit run --all-files` from that worktree. CI adds hassfest and
   HACS validation, which a local run cannot do.

Packaging references: [HACS integrations](https://hacs.xyz/docs/publish/integration/)
and [Home Assistant brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/).
