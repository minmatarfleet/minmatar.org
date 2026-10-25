# Fleet invites and private fleets

Any fleet's FC can invite pilots over Discord DM from the fleet's Invites tab: new pilots who haven't flown with us yet, friends, a tribe group or a corporation. Each pilot answers with the characters and ships they're bringing, says I'm in with no ship yet, or says they're sitting out.

A private fleet is an alliance fleet that only the invited know about. It never goes on the schedule. Pilots who are in join a private coordination thread under the audience's channel (#pings for the alliance audience), where the start ping goes. Everything else about the fleet works as usual.

Wireframes: the "Private Fleets" and "Standard Fleet Invites" design canvases (Oct 2026).

## Invites on a standard fleet

On a fleet that isn't invite only, an invite is a nudge, not access: the fleet stays on the schedule and gets its usual start ping.

| Rule | |
|---|---|
| Who invites | The fleet's FC (its creator) and superusers, while the fleet is upcoming. |
| New pilots | The Invite pilots dialog's New pilots tab invites the alliance health page's onboarding lists from the latest snapshot: First week (in the alliance 7 days or less, no fleets) and Under 3 fleets (past their first week, fewer than 3 fleets); `classify_onboarding_need` in `alliance/helpers/hygiene.py`. The Invites tab's empty state counts the first list. |
| Weekly cap | A pilot gets at most 2 Non-Strategic or Training fleet invites in a rolling 7 days (`WEEKLY_INVITE_CAP`). An invite counts once it's made, unless its DM couldn't be delivered. Strategic and private fleet invites don't count and aren't capped. |
| Stop fleet invites | A button on a Non-Strategic or Training invite DM. It turns off the `fleets.invite` Discord notification preference, which Account › Notifications shows and can turn back on. Pilots who turned it off are skipped; Strategic and private fleet invites still reach them. |
| The DM | "{FC} would like you on this fleet", the note, when, form-up and doctrine. Pilots invited from a new pilot list also get a link to the Your First Fleet guide. No opsec line. |
| I'm in, no ship yet | From the fleet page's invite banner. The FC sees "No ship yet" in the Bringing column. Picking a ship later says I'm in too. |
| Invited as | Each invite keeps why the pilot was invited (`source_kind`: `first_week`, `more_fleets`, `pilot`, `tribe_group`, `corporation`, and the group or corp's name). A new pilot list wins, then by name, then a group, then a corporation. |

## Rules

| Rule | |
|---|---|
| Who can make one | Strategic FCs only (`fleets.manage_any`). It's an alliance fleet: never a tribe group fleet, never on a campaign. Set on create (`invite_only` on `POST /api/fleets`); copying a fleet keeps it. |
| Who can see it | Invited players (whatever they answered), its creator, Strategic FCs and superusers. Everyone else gets a 404 from every `/api/fleets/{fleet_id}/…` route (`fleets/router.py` wraps them all), as if it didn't exist: a 403 would confirm it does. |
| Lists | Upcoming, History, Results and the desktop app show it only to its creator, Strategic FCs, and invitees who said I'm in. |
| Who invites | The creator and Strategic FCs. Invitees can't forward an invite; they can bring any of their own characters. |
| Answers | Picking a ship on the fleet page is I'm in. Sitting out clears the pilot's ships. A pilot can change their answer until the fleet starts. |
| Sending | On any fleet, Invite pilots picks tribe groups, corporations and pilots (search, or paste a list of primary character / Discord names), or invites one pilot from the tab's search; players already invited (and the creator) are left out. The FC never sees waves: each send is stored as one (`EveFleetInviteWave`) for its picks, note and pacing. One bulk send goes out at a time, at most 300 players; a single pilot can be invited alongside it. On a private fleet, a Strategic FC can Re-ping no answers: it DMs everyone who hasn't answered a short "Still coming?" nudge, as a reply to their invite DM (which has the details): hit Sitting out so the FC isn't waiting. At most once every 15 minutes. |
| Opsec line | Every DM, the thread summary and the top of the fleet page say: "Invite only. Don't mention this fleet in any channel, on comms or in chat." |
| Thread | A private, not invitable Discord thread named `Op <id>` (the name shows in the audit log). The bot adds the creator and every Strategic FC when the fleet is created, and each pilot who says I'm in; Sitting out removes them. A pinned summary shows the ship targets. The bot locks and archives it when the fleet ends or is cancelled. |
| Start ping | Posted once in the thread with `@everyone`, which in a thread reaches only its members. The sender checks the thread is a private thread (channel type 12) first and refuses otherwise. Never a pre-ping. |
| After the fleet | Hidden until its creator or a Strategic FC declassifies it (`POST /api/fleets/{id}/declassify`, once it's over). It then shows in History and Results and counts in every metric. Invites, answers, the leak trace and the thread stay private. |
| Leak trace | Each invite keeps its send, why the pilot was invited, when the DM went out, the answer and when the pilot first opened the fleet page (`first_viewed_at`). Only Strategic FCs see the last one, and only on a private fleet. |

## What leaves out an undeclassified private fleet

- `fleets.helpers.visibility.alliance_fleets_q` (fleet metrics, results, FC stats, surveys) and `visible_fleets_q` (v3 lists, the desktop app's Recent tab).
- `groups.helpers.feature_access.fleet_hidden_from`, so every `can_use_feature(..., fleet=...)` check fails for people who can't see it.
- The #schedule message (`fleets.tasks.update_fleet_schedule`, even once declassified), the public feed (`feed.router.members_only_fleet_ids`) and the corp pages' attendance (`eveonline.helpers.corporations.about`).
- Pre-pings (`send_discord_pre_ping`) and the audience start ping (`EveFleet.notify_discord`).

## Ship targets

Any fleet can have ship target lines: a name, a count and the hulls (`ship_type_ids`) or EVE groups (`group_ids`) that count, e.g. 40 Dreads, 40 TFIs, 20 Logistics. A hull or group may sit on one line only; each signed-up character counts once per line. `GET`/`PUT /api/fleets/{id}/targets`.

Every surface shows a line the same way (`ShipTargetMeter`): the name, a bar and one number, how many more are needed (orange) or Met (green). Lines keep the FC's order.

- **Ships tab** (`partials/fleet_ship_targets_component`): managers edit one line at a time (name, how many, hulls or groups from a search; one already on another line says so, and picking it moves it). With no lines yet, they start from the fleet's doctrine, one line per EVE group with its hulls filled in (`GET …/targets/suggestions`), or copy a past fleet's lines (only fleets they created). Hulls signed up on no line are listed for managers (`GET …/targets/unmatched`).
- **Find pilots** (fleets that haven't ended, for whoever manages their invites): lists alliance players not yet invited who own a hull for a short line, from ESI assets, nearest the form-up first (`GET …/targets/{target_id}/owners`); Invite invites them.
- **Ship picker**: Still needed bars, each option says which line it fills and whether it's still needed, hulls a character owns come first, and a character not bringing anything is offered an owned hull for a short line (`GET …/targets/mine`).
- **Invites tab, Invite pilots reach panel and thread summary**: the same lines; the pinned summary says `14 / 40 · 26 needed` or `✓ Met`.

## Sending

DMs go out from `fleets.tasks.send_fleet_invite_wave` at about one a second, not one task per player: opening many new DM channels at once trips Discord's anti-spam (error 40003). Thread adds are paced the same way. The DM is sent by `fleets.helpers.private_fleet_discord.send_invite_dm` (not `notify_user`: an invite can't be muted, and must carry its own buttons); its message id is kept so the bot can edit it once the pilot answers, when the fleet starts, and if it's cancelled (on any fleet).

## Data and API

- `EveFleet.invite_only`, `declassified_at`, `discord_thread_id`, `discord_summary_message_id`.
- `EveFleetInviteWave` (fleet, number, sent_by, note, the picks including `onboarding` buckets, finished_at) and `EveFleetInvite` (fleet, wave, user, answer, answered_at, source_kind, source_name, first_viewed_at, sent_at, dm_delivered, the DM's ids, in_thread). One invite per fleet and user.
- `EveFleetShipTarget` (fleet, name, target, order, ship_type_ids, group_ids).
- FC (and Strategic FCs on a private fleet): `GET /api/fleets/{id}/invites`, `POST …/invites/preview`, `POST …/invites/waves` (`onboarding: ["first_week", "more_fleets"]` on a standard fleet), `POST …/invites/reping` (private fleets, Strategic FCs only: `can_reping`), `GET …/invites/candidates?q=&pilots_only=` (each row says why it can't be invited: `invited`, `opted_out`, `capped`), `POST …/invites/resolve` (paste of character / Discord names), `POST /api/fleets/{id}/declassify`.
- Pilots: `POST /api/fleets/{id}/invites/me/out`, `POST /api/fleets/{id}/invites/me/in` (I'm in, no ship yet). The bot's Sitting out button (`fleet_invite:out:<invite id>`, `bot/app/fleet_invites`) calls `POST /api/fleets/invites/{invite_id}/discord-out`; Stop fleet invites (`fleet_invite:stop:<invite id>`) calls `POST /api/fleets/invites/{invite_id}/discord-stop`.
- `DISCORD_PRIVATE_FLEET_CHANNEL_ID` overrides the thread's parent channel; unset, it's the audience's channel. The bot needs Create Private Threads, Manage Threads and Mention Everyone there.

## Website

- New fleet form: "Invite only" switch for Strategic FCs.
- Fleet page: on a private fleet the opsec banner (with Open coordination thread and I'm sitting this one out); on a standard fleet an invited pilot's banner (`FleetInviteBanner.astro`: pick a ship, I'm in with no ship yet, Sitting out, and the first fleet guide for new pilots). Invites tab for whoever manages invites, Ship targets on the Ships tab, Still needed in the ship picker, Declassify on the Settings tab.
- Invites tab (`FleetInvites.astro`): one panel with the ship targets, then every invited pilot. The header invites one pilot from a search (`partials/fleet_invite_candidates_component?mode=single`; pilots who can't be invited say why) or opens Invite pilots. The status tiles split the pilots once (In, Sitting out, No answer, Not delivered = pending with a failed DM), filter the list, and carry the follow-ups: Re-ping under No answer (private fleets, Strategic FCs only), Copy fleet link under Not delivered. Columns: Pilot, Invited as, Status, Bringing ("No ship yet" for I'm in without ships), Answered, and Opened on a private fleet for Strategic FCs. The Bringing column names a character only when it's an alt.
- Invite pilots (`FleetInviteDialog.astro`): New pilots (standard fleets), Select names (groups, corporations and pilots) or Paste names, a note, a preview of the DM, and the reach panel (`FleetWavePreview.astro`: who gets a DM, who is skipped and why, who owns a hull for each short line).
