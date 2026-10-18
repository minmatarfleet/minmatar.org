# Frontend SDE snapshot

The frontend reads static EVE data (systems, moons, planets, ship slots and
attributes, type names) from a local SQLite copy of CCP's static data export
(SDE), in the Fuzzwork table layout (`invTypes`, `invGroups`, `mapSolarSystems`,
...). The Drizzle schema for it is `frontend/app/src/models/sde/schema.ts`.

## Where it lives

- File: `frontend/app/src/data/sde-<build>.sqlite`, where `<build>` is CCP's
  SDE build number. It is about 550 MB and is not in git (`sde-*.sqlite` is
  ignored).
- The build the site expects is `SDE_BUILD` in
  `frontend/app/src/helpers/sde_path.mjs`. That file is the one config point:
  the site (`helpers/sde_db.ts`), drizzle-kit (`sde.drizzle.config.ts`) and the
  report extractors (`scripts/warzone_extract.mjs`,
  `scripts/amamake_market_extract.mjs`) all resolve the path through it.
- `SDE_FALLBACK_BUILDS` lists older builds that are still accepted, with a
  warning in the log, while hosts are upgraded. Empty it once every host has
  the pinned file.
- `SDE_PATH=/some/file.sqlite` overrides the lookup (tests, one-off runs).
- Production: `docker-compose-prod.yml` mounts `./frontend/app/src/data` into
  the frontend container, so the file must be on the host. The Docker image
  build does not need it.

If no usable file is found, the first SDE query throws
`SDE snapshot missing: expected src/data/sde-<build>.sqlite ...`. Importing a
helper does not open the file, so `npm run check`, `npm run test` and
`astro build` work without it (the tests that query it skip when it is missing).

## Provision or upgrade it

1. Download the Fuzzwork SQLite conversion of the SDE from
   <https://www.fuzzwork.co.uk/dump/> and decompress it
   (`bunzip2 sqlite-latest.sqlite.bz2`). Note the CCP build number it was made
   from.
2. Save it as `frontend/app/src/data/sde-<build>.sqlite`.
3. If the build is new, set `SDE_BUILD` in `src/helpers/sde_path.mjs` and move
   the previous build into `SDE_FALLBACK_BUILDS`.
4. If the table layout changed, run `npm run introspectsde` and review the
   schema diff.
5. Run `npm run sde:check` from `frontend/app/`. It prints the file it will
   open, the build, the size, the sha256 and the newest type ID. Record the
   sha256 below, and copy the same file to every host's
   `frontend/app/src/data/` before deploying the change.

| Build   | sha256 | Notes |
|---------|--------|-------|
| 3409592 | (record on provisioning) | Pinned: the build the site has preferred since June 2026. |
| 3316380 | (record on provisioning) | Fallback. Some dev machines have this name as a symlink to the 2024-09-20 Fuzzwork dump, which is older than the build; `sde:check` shows the newest type ID so you can tell. |

## What should not come from the SDE

Live data should carry its names from the backend. The campaign killfeed
(`CampaignKillfeed.astro`) still resolves victim ship names through the
snapshot because the killmail payload only has `victim_ship_type_id`, so a hull
CCP added after the snapshot shows without a name until the SDE is upgraded.
