# Desktop app versioning and releases

The desktop app (`desktop/`) releases itself: merging to `main` publishes a GitHub release whenever `desktop/package.json` has a version that hasn't been released yet (`.github/workflows/desktop.yml`). Installed apps auto-update from that release. **Bumping the version is the release button.**

## When to bump

Only bump when the user says the desktop changes are ready to release. Changing `desktop/` without a bump is fine: it merges without releasing, and the PR check posts a notice saying so.

## How to bump (semantic versioning)

Pick the level from what changed since the last release (`git log v<last>..HEAD -- desktop`):

- **patch** (`0.4.0` → `0.4.1`): bug fixes, timing/visual tweaks, no new behaviour.
- **minor** (`0.4.1` → `0.5.0`): new features or settings, new windows, new log-engine events.
- **major** (`0.x` → `1.0.0`, `1.4.2` → `2.0.0`): breaking changes, such as a stored-session or settings format change that signs everyone out or resets settings, dropping Windows support, or a minimum backend/API version requirement.

Run the bump from `desktop/` so `package.json` and `package-lock.json` stay in sync. On Windows (npm doesn't run on the WSL share), copy the folder out as the desktop README describes:

```bash
npm version minor --no-git-tag-version
```

Commit it as its own commit, e.g. `Release desktop v0.5.0`, with a short list of what changed. Don't create tags by hand; the workflow tags the merge commit.

## Rules

- Never reuse or lower a released version. The PR check fails if you do.
- Never create GitHub releases tagged `v*` for anything else on this repo: the updater installs whatever release is "latest".
- Every new feature must pass `docs/desktop/ccp-third-party-guidelines.md` before it ships.

## Account settings are shared by every installed version

Desktop settings live on the pilot's account (`/api/users/me/desktop-settings`, saved as a merge of the changed keys), not on the PC. Two PCs, or an installer and a portable exe, can run different app versions against the same keys at the same time. The keys and their shapes are listed in `desktop/src/main/settings_schema.js`: `locked`, `show_sneak`, `fade_on_right_click`, `window.<id>` (`enabled`, `bounds`, intel's `range`) and `fleet_reminders`.

- **Never change the shape or meaning of an existing key or field.** For a new shape, use a new key name and have the new version read the old key as a fallback. Changing an existing key in place is a **major** version, because it breaks the pilot's other installs.
- Adding a key or a field is fine (minor). Older versions ignore it.
- Read every key through `settings_schema.js`. An invalid or unknown value reads as the default, and a read never writes, so this version never "fixes" another version's value on the account.
- When writing an object key, spread the stored value first (`stored_window`), so fields added by a newer version survive. Leave keys you don't know alone.

## The backend contract with installed versions

Every backend change to an endpoint the desktop calls ships at once to every installed copy, and portable builds never update themselves, so some pilots run old versions for months. The desktop-facing endpoints are the ones in `desktop/src/main/api.js`: `/api/campaigns/overlay`, `/api/fleets/window/*`, `/api/fleets/{id}/window`, `/api/fleets/v3`, `/api/users/me/desktop-settings`, `/api/intel/*` and the few others listed there.

- **Changes are additive.** Add fields and endpoints freely; older versions ignore them. Never rename, retype, or change the meaning of a field a released version reads. Ship the new name next to the old one instead.
- **Removal needs a deprecation window.** Every desktop request carries `X-Minmatar-Client: desktop/<version> (<installer|portable>)` (from `app.getVersion()`), and the backend counts it per day (`app/client_versions.py`; `manage.py api_clients --days 30`, or the `client` tag in Sentry). Remove a field only after the last release that reads it has stopped showing up for 30 days. Releases up to 0.10.x send no header; treat requests to desktop endpoints with a Node user agent and no header as those.
- **The payloads are pinned by contract files.** `desktop/test/contracts/*.json` are written by backend tests from the real endpoints (`backend/app/contracts.py`), and the desktop tests render from them. A backend change that alters one fails backend CI; if it is intended and additive, regenerate with `UPDATE_CONTRACTS=1 python manage.py test <the contract test>` and commit the file. Editing a contract file is a desktop-visible change, and it runs the desktop CI.
- **New desktop code tolerates older backends**: check that a field is present before relying on it (as `load_campaign` does with `change_week`), because the backend may deploy after the app updates.
- **Website pages the desktop opens are part of the contract too.** They are listed in `desktop/src/main/web_routes.js` (the backend's are in `backend/app/web_links.py`). When the website moves one, keep the old path working or redirect it: released versions keep opening it.
- A change that needs a minimum backend or drops an old endpoint is a **major** desktop version.
