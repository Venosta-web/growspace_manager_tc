# V1 release verification

## Test environment

The workspace issue [#119](https://github.com/Venosta-web/growspace_manager_workspace/issues/119)
uses the hub's clean `ha-test` instance at `http://localhost:8124`. Its only
mount is the host configuration directory; no integration source or card build
is mounted into it. HACS downloads the integrations and card from GitHub.

The verification starts with HACS and an onboarded owner, but no Growspace
Manager or TC integration or records. This preserves HACS authentication without
copying development-instance state. The local runtime now supports passwordless
trusted-network login; this is test configuration, not a TC installation step.

## Reproduce

1. Start the hub's `./scripts/ha test up`. On a fresh instance, finish Home
   Assistant and HACS onboarding. Use only `ha-test`, never the dev instance.
2. Add Growspace Manager and TC as HACS custom repositories of type Integration,
   and the Growspace Manager card as type Dashboard. Download the intended refs.
   GM's `zip_release` packaging requires a published release, not `main`.
3. Restart the test instance. Try adding TC before configuring GM: it must
   explain that Growspace Manager is missing. Configure GM, then add TC.
4. Add a GM phenotype and an empty growspace. Add a dashboard using the
   HACS-registered card resource and open TC. Follow the README's first loop.
5. Verify Introduction; immutable medium edits; Replate with a split, counts,
   Locations, and pinned version; notes; rooting; Discard; pairing create,
   edit, both projections, and delete; and optional Graduation into a plant.
6. Verify the returned plant ID exists in GM, opt-out retains a plain
   graduation, and bridge failure also retains a plain graduation. Check one
   TC calendar, due dates, ended Culture history, and persistence after restart.
7. Confirm that no derived-statistics, import/export, or overdue alert entity
   surface has been introduced. Review the manifest feature list and entity
   registry against `docs/v1-scope.md`.
8. Run from the main hub, with the TC worktree explicitly selected:

   ```bash
   GROWSPACE_TC=/path/to/growspace_manager_tc/.worktrees/release-readiness \
     ./scripts/check tc full
   ```

   Run `pre-commit run --all-files` from that TC worktree as well. CI runs
   hassfest and HACS validation. Local brand images are supported by the
   declared Home Assistant floor; HACS's remote `brands` check remains ignored.

## Verification record

Verification in progress for the prepared 1.0.0 candidate. The final record
will identify the downloaded refs and distinguish HACS installation from
browser checks. No V1 GitHub release has been published by this change.

Packaging references: [HACS integrations](https://hacs.xyz/docs/publish/integration/)
and [Home Assistant local brand images](https://developers.home-assistant.io/docs/core/integration/brand_images/).
