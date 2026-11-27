# Group fleet roundup and corporation forwarding

Asked for by the Mining group (Industry tribe) on 2026-11-27. This file
describes what is built; rules 2 and 3 of `docs/tribes/tribe-publishing.md`
point here.

## Why

Miners plan fleets days ahead (for example Monday, Tuesday, Wednesday and
Friday), unlike PvP fleets that form on the spot. A daily look at the coming
fleets lets pilots plan around them, so more of them turn up to the same
fleets.

Many Mining pilots are in M-EXC, an Associate corporation. Associates cannot
see `#schedule`, and M-EXC runs its own Discord server with a mining ping
channel. The fleet posts should reach that channel too.

## What it does

### 1. Daily roundup in the group's channel

- Once a day, at an hour the group's chiefs choose (default 20:00 EVE), the
  bot posts one message to the group's channel (else its tribe's channel,
  the same choice as the quiet pre-ping).
- It lists the group's fleets in the next 5 EVE days, starting tomorrow
  (00:00 EVE tomorrow until 23:59 EVE on day 5), grouped by day, with
  "Tomorrow" first. Days without fleets are left out.
- No fleets in those 5 days: nothing is posted.
- Silent: no mentions, Discord silent flag (4096), like the quiet pre-ping.
- Old roundups are kept. The bot never deletes a roundup; the channel is
  also used for chat, and deleting would break replies to it.
- Each line: emoji, EVE time, local time (`<t:…>`), FC, objective or
  doctrine, link to the fleet page (the page always shows the current
  status, so a fleet moved or cancelled since an old roundup is clear
  there).
- Leaves out cancelled fleets, private (invite-only) fleets, and standing or
  campaign fleet types, as `#schedule` does.
- Off by default. A group's chiefs turn it on; groups that don't are
  unchanged.

```
### Mining fleets — next 5 days
**Tomorrow, Tue 2 Dec**
- ⛏️ 18:00 EVE (<local>) Keldar · Gukarla moon belt
**Wed 3 Dec**
- ⛏️ 19:00 EVE (<local>) Another FC · Amo ice
-# Sign up on the fleet page.
```

### 2. Forwarding to a corporation's own Discord server

- On the corporation's Settings tab (CEO, directors: the existing
  `can_edit_corporation_settings`), next to the linked Discord server, the
  corporation picks a **fleet ping channel** in that server and the tribe
  groups whose fleet posts it follows.
- Only works with the bot linked through the existing corporation Discord
  bot flow (`eveonline/helpers/corporations/discord_bot.py`); the bot only
  posts into a server the corporation linked itself.
- Only the bot's own fleet posts for followed groups are copied, nothing
  else: the bot does not read the group's channel. Each post is sent to
  both places when it is created.

| Post | Group channel | Corporation channel |
|---|---|---|
| Daily roundup | silent | silent |
| Quiet pre-ping | silent | silent |
| Start ping | group role | `@here` |

- Private (invite-only) fleets are never forwarded.
- A corporation gets the roundup only when the group has it turned on, at
  the group's hour.
- A pre-ping or start ping still needs the group's own channel (else its
  tribe's); it is never sent only to corporations.
- The start ping preview on the fleet form names the corporations it also
  goes to (`also_posted_to`).
- Changing the channel of a follow (on the corporation's Settings) needs a
  new approval.
- A follow stops forwarding at once when the corporation is no longer
  Alliance or Associate, or its bot leaves the server
  (`TribeGroupCorporationFollow.is_forwarding`).
- Any Alliance or Associate corporation with the bot linked can ask to
  follow a group.
- **A group's chiefs approve it.** The corporation's request does nothing
  until someone who can manage the group (`user_can_manage_group`) accepts
  it on the group's page. They can revoke it at any time, and the
  corporation can stop following at any time. While a request waits, or
  after it is revoked, nothing is forwarded. (Decided 2026-11-27.)

### Bot permissions in the corporation's server

Posting needs **Send Messages** and **Embed Links**, and `@here` only
notifies anyone with **Mention @everyone, @here and All Roles**.

- A corporation's bot install asks for these too
  (`CORPORATION_INSTALL_PERMISSIONS` in
  `eveonline/helpers/corporations/discord_bot.py`). Tribe servers share
  the install link and keep `INSTALL_PERMISSIONS`.
- Servers linked before this (M-EXC) grant them to the bot in the chosen
  channel, or reconnect the bot.
- Settings > Fleet pings computes the bot's permissions in each followed
  channel and warns: `channel_missing`, `cant_post`, `no_embeds`, `no_here`. A failed post
  (unknown channel, missing access or permissions) is recorded on the
  follow and shown there and on the group's list.

## How it is built

**One shared "where does this group post go" step**,
`tribes/helpers/fleet_post_destinations.py`. Every group fleet post asks it
for its destinations (the group's channel, then each forwarding follow) and
applies each one's mention rule from the table above (`send_group_post`).
The pre-ping (`fleets/endpoints/helpers.py`), the start ping
(`EveFleet.notify_discord` in `fleets/models.py`) and the roundup task call
it; a new post type gets forwarding the same way.

Considered and not chosen:

- Adding a separate "also post to the corporation" step to each of the
  three posts: same work now, but three places to keep in sync.
- Discord's own Follow channel: needs an announcement channel instead of
  the chat channel, can't `@here`, and the site can't tell when it breaks.

Data and code:

- `TribeGroup.roundup_enabled`, `roundup_hour` (EVE, 0-23, default 20) and
  `roundup_last_sent_on`, set in the group's Chiefs tab > Discord by
  anyone who can manage the group (`PATCH /api/tribes/groups/{id}/publishing`).
- `tribes.TribeGroupCorporationFollow`
  (`tribes/models/tribe_group_corporation_follow.py`): corporation, group,
  channel, status (`requested`, `approved`, `revoked`), who decided and
  when, and the last delivery.
- The message: `fleets/helpers/group_roundup.py`. The task
  `tribes.tasks.post_group_fleet_roundups` runs hourly and posts once per
  EVE day, at the first run at or after the group's hour, so a missed run
  posts later that day. A day without fleets counts as done. Archived
  groups, groups in an archived tribe and groups with fleets switched off
  post none. One failing group is logged and retried next hour without
  stopping the others.
- Corporation posts go through `tribes.tasks.post_forwarded_fleet_message`,
  which rechecks the follow before posting and records the result. The
  group's own posts go through the outbox (`discord/outbox.py`).
- API: corporations use `GET`, `PUT` and `DELETE`
  `/api/eveonline/corporations/corporations/{id}/discord/fleet-follows[/{group_id}]`
  (CEO and directors); a group's managers use
  `GET /api/tribes/groups/{id}/corporation-follows` and
  `POST .../corporation-follows/{follow_id}` with `approve` or `revoke`.
- Website: the group's Chiefs tab (roundup switch and hour, and the
  corporation list with Approve and Revoke), and the corporation's
  Settings > Fleet pings.

## Rule changes (docs/tribes/tribe-publishing.md)

- Rule 3 gains the roundup (silent, group's channel) and the forwarded
  copies (silent, start ping with `@here` in a corporation's server). Group
  fleets still never ping `@everyone`.
- Rule 2 gains an exception: a members-only group item may also be pinged
  "in a corporation's channel the group's chiefs approved" (decided
  2026-11-27: the corporation asks, a chief approves).

## Non-goals

- Forwarding chat, reactions or other bot messages.
- Changing `#schedule` or alliance fleet pings (rule 1).
- Pinging a role in the corporation's server.
