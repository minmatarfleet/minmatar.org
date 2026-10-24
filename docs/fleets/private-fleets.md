# Private fleets

A private fleet is an alliance fleet that only the invited know about. It never goes on the schedule. The FC invites pilots in waves over Discord DM; each pilot answers with the characters and ships they're bringing, or says they're sitting out. Pilots who are in join a private coordination thread under the audience's channel (#pings for the alliance audience), where the start ping goes. Everything else about the fleet works as usual.

Wireframes: the "Private Fleets" design canvas (Oct 2026).

## Rules

| Rule | |
|---|---|
| Who can make one | Strategic FCs only (`fleets.manage_any`). It's an alliance fleet: never a tribe group fleet, never on a campaign. Set on create (`invite_only` on `POST /api/fleets`); copying a fleet keeps it. |
| Who can see it | Invited players (whatever they answered), its creator, Strategic FCs and superusers. Everyone else gets a 404 from every `/api/fleets/{fleet_id}/…` route (`fleets/router.py` wraps them all), as if it didn't exist: a 403 would confirm it does. |
| Lists | Upcoming, History, Results and the desktop app show it only to its creator, Strategic FCs, and invitees who said I'm in. |
| Who invites | The creator and Strategic FCs, in waves. Invitees can't forward an invite; they can bring any of their own characters. |
| Answers | Picking a ship on the fleet page is I'm in. Sitting out clears the pilot's ships. A pilot can change their answer until the fleet starts. |
| Waves | A wave picks tribe groups, corporations and pilots (search, or paste a list of primary character / Discord names); players already invited (and the creator) are left out. One wave sends at a time, at most 300 players. Re-ping no answers DMs everyone who hasn't answered once more, at most once every 15 minutes. |
| Opsec line | Every DM, the thread summary and the top of the fleet page say: "Invite only. Don't mention this fleet in any channel, on comms or in chat." |
| Thread | A private, not invitable Discord thread named `Op <id>` (the name shows in the audit log). The bot adds the creator and every Strategic FC when the fleet is created, and each pilot who says I'm in; Sitting out removes them. A pinned summary shows the ship targets. The bot locks and archives it when the fleet ends or is cancelled. |
| Start ping | Posted once in the thread with `@everyone`, which in a thread reaches only its members. The sender checks the thread is a private thread (channel type 12) first and refuses otherwise. Never a pre-ping. |
| After the fleet | Hidden until its creator or a Strategic FC declassifies it (`POST /api/fleets/{id}/declassify`, once it's over). It then shows in History and Results and counts in every metric. Invites, answers, the leak trace and the thread stay private. |
| Leak trace | Each invite keeps its wave, when the DM went out, the answer and when the pilot first opened the fleet page (`first_viewed_at`). Only Strategic FCs see the last one. |

## What leaves out an undeclassified private fleet

- `fleets.helpers.visibility.alliance_fleets_q` (fleet metrics, results, FC stats, surveys) and `visible_fleets_q` (v3 lists, the desktop app's Recent tab).
- `groups.helpers.feature_access.fleet_hidden_from`, so every `can_use_feature(..., fleet=...)` check fails for people who can't see it.
- The #schedule message (`fleets.tasks.update_fleet_schedule`, even once declassified), the public feed (`feed.router.members_only_fleet_ids`) and the corp pages' attendance (`eveonline.helpers.corporations.about`).
- Pre-pings (`send_discord_pre_ping`) and the audience start ping (`EveFleet.notify_discord`).

## Ship targets

Any fleet can have ship target lines: a name, a count and the hulls (`ship_type_ids`) or EVE groups (`group_ids`) that count, e.g. 40 Dreads, 40 TFIs, 20 Logistics. A hull or group may sit on one line only; each signed-up character counts once per line. `GET`/`PUT /api/fleets/{id}/targets`.

Every surface shows a line the same way (`ShipTargetMeter`): the name, a bar and one number, how many more are needed (orange) or Met (green). Lines keep the FC's order.

- **Ships tab** (`partials/fleet_ship_targets_component`): managers edit one line at a time (name, how many, hulls or groups from a search; one already on another line says so, and picking it moves it). With no lines yet, they start from the fleet's doctrine, one line per EVE group with its hulls filled in (`GET …/targets/suggestions`), or copy a past fleet's lines (only fleets they created). Hulls signed up on no line are listed for managers (`GET …/targets/unmatched`).
- **Find pilots** (private fleets that haven't ended, creator and Strategic FCs): lists alliance players not yet invited who own a hull for a short line, from ESI assets, nearest the form-up first (`GET …/targets/{target_id}/owners`); Invite sends them as the next wave.
- **Ship picker**: Still needed bars, each option says which line it fills and whether it's still needed, hulls a character owns come first, and a character not bringing anything is offered an owned hull for a short line (`GET …/targets/mine`).
- **Invites tab, wave preview and thread summary**: the same lines; the pinned summary says `14 / 40 · 26 needed` or `✓ Met`.

## Sending

DMs go out from `fleets.tasks.send_fleet_invite_wave` at about one a second, not one task per player: opening many new DM channels at once trips Discord's anti-spam (error 40003). Thread adds are paced the same way. The DM is sent by `fleets.helpers.private_fleet_discord.send_invite_dm` (not `notify_user`: an invite can't be muted, and must carry its own buttons); its message id is kept so the bot can edit it once the pilot answers, when the fleet starts, and if it's cancelled.

## Data and API

- `EveFleet.invite_only`, `declassified_at`, `discord_thread_id`, `discord_summary_message_id`.
- `EveFleetInviteWave` (fleet, number, sent_by, note, the picks, finished_at) and `EveFleetInvite` (fleet, wave, user, answer, answered_at, first_viewed_at, sent_at, dm_delivered, the DM's ids, in_thread). One invite per fleet and user.
- `EveFleetShipTarget` (fleet, name, target, order, ship_type_ids, group_ids).
- FC and Strategic FCs: `GET /api/fleets/{id}/invites`, `POST …/invites/preview`, `POST …/invites/waves`, `POST …/invites/reping`, `GET …/invites/candidates?q=`, `POST …/invites/resolve` (paste of character / Discord names), `POST /api/fleets/{id}/declassify`.
- Pilots: `POST /api/fleets/{id}/invites/me/out`. The bot's Sitting out button (`fleet_invite:out:<invite id>`, `bot/app/fleet_invites`) calls `POST /api/fleets/invites/{invite_id}/discord-out`.
- `DISCORD_PRIVATE_FLEET_CHANNEL_ID` overrides the thread's parent channel; unset, it's the audience's channel. The bot needs Create Private Threads, Manage Threads and Mention Everyone there.

## Website

- New fleet form: "Invite only" switch for Strategic FCs.
- Fleet page: opsec banner (with Open coordination thread and I'm sitting this one out), Invites tab for the creator and Strategic FCs, Ship targets on the Ships tab, Still needed in the ship picker, Declassify on the Settings tab.
- Invites tab (`FleetInvites.astro`): one panel with the ship targets, then every invited pilot across waves. The status tiles split them once (In, Sitting out, No answer, Not delivered = pending with a failed DM), filter the list, and carry the follow-ups: Re-ping under No answer, Copy fleet link under Not delivered. A wave picker shows that wave's audience, sender and note. Send wave opens a dialog (`FleetWaveDialog.astro`) with search or a pasted list, a note, a preview of the DM, and the reach panel (`FleetWavePreview.astro`: who gets a DM, who is skipped, who owns a hull for each short line). The Bringing column names a character only when it's an alt.
