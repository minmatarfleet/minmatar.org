# Minmatar Fleet desktop app

An Electron app for Windows that signs you in with Discord, the same way my.minmatar.org does, and shows **Upcoming Fleets** in an EVE-styled window. You can pin that window as a glass overlay over the EVE client.

## What it does

- **Discord sign-in.** The app calls the backend's existing `GET /api/users/login?redirect_url=…`. The backend sends your browser to Discord, then redirects back to `redirect_url?token=<JWT>`, exactly as it does for the website. The desktop app's `redirect_url` is a one-shot listener on `http://127.0.0.1:<random port>/callback/<random nonce>`, so the token goes straight to the app. No backend changes were needed.
- **Token storage.** The JWT is encrypted with Electron `safeStorage` (Windows DPAPI, tied to your Windows account) in `%APPDATA%\Minmatar Fleet\session.bin`. It is only ever used from the main process as `Authorization: Bearer …`; the windows never see it. **Sign out** deletes it.
- **Upcoming Fleets.** Shows the same list as the website's Upcoming Fleets page (`GET /api/fleets/v3?fleet_filter=active`), with FC names from `/api/users/profiles`, doctrine names from `/api/doctrines/{id}`, EVE-time start, and a live countdown. It refreshes every minute while it's on screen. Click a fleet to open it in the window.
- **Fleet view.** When you're in a fleet (or open one from the list), the same window shows that fleet, from one call: `GET /api/fleets/window/current` (or `/api/fleets/{id}/window` for a fleet you opened). What you see depends on who you are:
  - **FC** (you created the fleet, or one of your characters is the in-game boss): pilots in fleet, how many are with you, kills and losses, each doctrine ship flying vs signed up, roles nobody covers, and the pilots who need a nudge (in a pod, off doctrine, docked, not with the fleet). The **Pilots** tab is the roster; only the FC gets it. **Refresh MOTD** pushes the in-game MOTD. At the window's minimum size this becomes a glance strip.
  - **Member**: your ship (doctrine ship or not), how many jumps you are behind the fleet, what the fleet is short of, and the doctrine fits to copy as EFT. No roster.
  - **Not in it yet**: countdown, form-up place and jumps, and the ships to pick from; picking one signs you up (`PUT /my-ship-volunteers`).
  - **Ship lost**: shown once per loss, with SRP (the killmail link goes on your clipboard) and where to reship. **After-action** (FC, once the fleet closes): ISK killed vs lost and what's still open (AAR link, unfiled SRP).

  "You" is always the character whose EVE client is in front. Jumps come from ESI's public route API, asked once per pair of systems.
- **Overlay windows** live on EVE: they sit directly on top of the client, never take focus from the game, and let clicks pass through everywhere except their buttons and rows. They show while a logged-in EVE client is on screen (an app brought in front of EVE covers them like it covers EVE) and hide otherwise. A client still at character select doesn't count. The pin button pins them in place; unpin to drag a window by its header and resize it from the corner. The background is a live blur of the game behind it.
- **Matches your EVE transparency.** The window background follows the **Settings → Windows** transparency (`windowTransparency`) of the character whose client is in front. That character is identified from its window title (`EVE - <name>`, resolved to an ID with ESI's public name lookup). The app reads it, read-only, from EVE's own `%LOCALAPPDATA%\CCP\EVE\*_tq_tranquility\settings_*\core_char_<id>.dat`. With no client in front it uses the last character that saved settings, and it picks up a changed value when EVE next saves the file. Only the background changes; text stays fully opaque.

- **Campaigns.** Your live Faction Warfare campaign (the one you're enlisted in, else the newest live one) from `GET /api/campaigns/overlay`. One line per system: who holds it, the objective, a bar for progress and its move since the week opened (▲ +8% wk / ▼ -3% wk), or Taken / Lost when the system changed hands this week. Hover a line for the exact figure and the last 24 hours' move. Complex objectives are measured in victory points, advantage objectives in advantage. Below that, portraits of the enlisted pilots who got a kill, captured a site or flew in a campaign fleet in the last hour; hover one for what they did. Narrow the window for a one-line-per-system strip. Off by default: turn it on in Settings.
- **Intel** (off by default; turn it on in Settings). Copy a d-scan or Local member list in EVE, click **Paste** (or Ctrl+V while the window has focus), check the preview (ship counts, or for Local the militia, alliance and standing breakdown) and click **Share**: the report goes to the alliance intel sheet (`POST /api/intel/reports`) and its my.minmatar.org link is copied for fleet chat. The window lists the last two hours of reports and the feed's capital and Amarr fleet pings (`GET /api/intel/recent`, every 30 s), biggest hulls first with the rest behind "+N". Jumps are counted on the PC from the SDE gate graph (`GET /api/intel/map`), so your location never leaves it.
- **Settings and Sneak.** Settings lists the overlay windows from `src/main/windows.js` so pilots pick which ones they use (Upcoming Fleets, Campaigns and Intel), plus the overlay toggles, account, version and updates. Open it by clicking **Sneak**, who peeks over EVE's notification badge, or from the gear button or the tray. Sneak's spot is computed from EVE's own settings: `notification_badge_offset` in `core_char_<id>.dat` (from the client's bottom-right corner, default 16,16) and the UI scale in `core_public__.yaml`. He only shows on a logged-in client, including while it's on screen under another app.
- **Version** is shown in every window's footer and in Settings.

It never reads EVE's memory, injects into the client, reads the screen, or sends input to the game. It only looks at which window is in front and where the EVE windows are.

## Use it

Install `MinmatarFleet-<version>-x64.exe`, or run the portable `.exe`. The builds are unsigned, so Windows SmartScreen will warn on first run: choose **More info → Run anyway**.

Run EVE in **Fixed Window** or **Window** mode. Overlays can't draw over true fullscreen.

## Develop

Everything runs on Windows. npm can't run inside `\\wsl.localhost`, so copy the folder to a Windows path first.

```
npm install
npm test                  # unit tests (node:test, no Electron needed)
npm start                 # against https://api.minmatar.org
npm run start:local       # against http://localhost:8000 + http://localhost:4321
npm run dist              # dist/MinmatarFleet-<version>-x64.exe (installer) + -portable.exe
npx electron-builder --win portable --publish never "-c.extraMetadata.version=0.4.0-dev.1"   # local test build, labelled as dev
```

Flags: `--api=<url>` / `--web=<url>` (or `MINMATAR_API_URL` / `MINMATAR_WEB_URL`), `--diag=<file>` for a JSON-lines event log, `--client-procs=exefile,powershell` to treat a stand-in window titled `EVE - <Name>` as a client while testing without the game.

| Path | |
|---|---|
| `src/main/auth.js` | Loopback Discord login + encrypted token store |
| `src/main/api.js` | API client and the fleet and campaign view models; ETag reads for polled calls |
| `src/main/fleet_window.js` | Fleet view: which fleet to show, polling, actions (copy fit, sign up, MOTD, SRP) |
| `src/main/route.js` | Jump counts from ESI's route API, cached per pair |
| `src/main/eve_clients.js` + `src/native/helper.cs` | Foreground/EVE-window tracking and glass, via a C# helper compiled at launch by PowerShell `Add-Type` (no native build step) |
| `src/main/eve_settings.js` | Reads EVE's window transparency from the client's settings files |
| `src/main/eve_logs/` | Chat/game log engine (below) |
| `src/main/overlay_rules.js` | When the windows show (on a logged-in client, under apps brought in front of it; screenshot tools and the taskbar don't hide them) |
| `src/main/main.js` | Windows, overlay mode, tray, refresh loop |
| `src/renderer/` | EVE-styled windows (`eve-window.css`, shared chrome in `eve_window.js`), sign-in, fleets and campaigns UI |

## Updates and releases

The **installer** build updates itself from this repo's GitHub Releases ([electron-updater](https://www.electron.build/auto-update), `src/main/updater.js`). It checks at start-up and every 4 hours and downloads new versions in the background. When an update is ready, the fleets window footer and the tray menu show **Restart to update**; otherwise the update installs the next time the app quits. The **portable** exe can't replace itself: it shows "v… available" and links to the release.

To release, bump the version and merge. It uses semantic versioning: **patch** for fixes, **minor** for features, **major** for breaking changes. The full rules are in [.claude/rules/desktop-release.md](../.claude/rules/desktop-release.md).

```
npm version minor --no-git-tag-version   # updates package.json + package-lock.json
```

`.github/workflows/desktop.yml` does the rest:
- **Pull requests** run the tests on Windows and check the version: it must be semver, move forward, and not reuse a released version. Changing the app without a bump is fine; the check just notes that merging won't release.
- **Pushes to `main`** that touch `desktop/` release only if `v<version>` has no published release yet. The workflow tags the commit, builds it on `windows-latest`, runs the tests, and publishes the installer, its `.blockmap`, `latest.yml` and the portable exe. A release that failed part-way is finished on the next run, or with **Run workflow**.

The updater installs whatever release GitHub marks as **latest** on this repo, so `v*` releases here are reserved for the desktop app. The builds are unsigned: Windows SmartScreen warns on the first install, and electron-updater does not verify a publisher for unsigned updates. A code-signing certificate fixes both (configure `win.signtoolOptions` / `CSC_LINK` in CI).

## EVE log engine

`src/main/eve_logs` tails the files EVE writes to `Documents\EVE\logs` and turns them into events and per-character state. Anything in the app can hook into it:

```js
const engine = new EveLogEngine({ logs_dir }).start()
engine.on('ready', snapshot => ...)       // state rebuilt from the last 36 h of logs, no replayed events
engine.on('system', e => ...)             // { character, from, to, time, source: 'local' | 'jump' }
engine.on('message', e => ...)            // chat line, once even if several of your characters saw it ({ listeners })
engine.on('chat', e => ...)               // chat line per listening character
engine.on('game', e => ...)               // game log line { kind: 'combat' | 'notify' | 'none' | …, text, html }
engine.on('combat', e => ...)             // + e.combat: damage / remote_repair / warp_disruption / warp_scramble / miss / neut / nos
const stop = engine.watch_channel(/intel/i, e => ...)
engine.character_by_name('Kaleb Snowden') // { id, name, system, system_since, last_jump, channels }
```

How it stays reliable:
- **Open files:** each file is read through its own handle from the last offset, because EVE keeps logs open for the whole session.
- **Split writes:** lines split mid-write (including mid UTF-16 character) are joined.
- **Multi-line messages:** MOTDs and similar stay one message.
- **Ordering:** lines from different files are dispatched in time order.
- **System changes:** one system change per jump, even though Local and the game log both report it.
- **Old files:** sessions older than 36 h are skipped by file name, without opening them.
- **Character select:** game logs opened before a character is chosen are ignored.

Against a real log folder (12,000+ chat files), start-up took about 0.4 s.

**Not in the logs:** fleet broadcasts, loot history and fleet member history exist only inside the client. A `Broadcast:` line in Fleet chat is MOTD text, not a broadcast. The current system needs **Log chat to file** enabled in EVE (on by default). The Local-change line is matched for English clients only.

Why it is built this way (glass API choice, overlay rules, CCP policy): [docs/desktop/overlay-technology.md](../docs/desktop/overlay-technology.md).

## Notices

© CCP hf. All rights reserved. "EVE", "EVE Online", "CCP", and all related logos and images are trademarks or registered trademarks of CCP hf. This application has been created under the EVE Developer License Agreement. It is a Minmatar Fleet alliance tool and is not affiliated with or endorsed by CCP hf. The same text is shown under **About** in the tray menu.

Before adding a feature, check it against [docs/desktop/ccp-third-party-guidelines.md](../docs/desktop/ccp-third-party-guidelines.md).
