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
