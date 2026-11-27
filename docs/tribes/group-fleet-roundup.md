# Group fleet roundup and corporation forwarding (concept)

Status: concept, nothing built yet. Asked for by the Mining group (Industry
tribe) on 2026-11-27.

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
  the group's hour (my call: one plan, one time).
- A pre-ping still needs the group's own channel, as today; it is never
  sent only to corporations (my call: the group's channel stays the
  source).
- The start ping preview on the fleet form lists the corporation channels
  it will also go to (my call).
- Any Alliance or Associate corporation with the bot linked can ask to
  follow a group.
- **A group's chiefs approve it.** The corporation's request does nothing
  until someone who can manage the group (`user_can_manage_group`) accepts
  it on the group's page. They can revoke it at any time, and the
  corporation can stop following at any time. While a request waits, or
  after it is revoked, nothing is forwarded. (Decided 2026-11-27.)

### Bot permissions in the corporation's server

The corporation bot install today asks only for Create Invite, View
Channel, Manage Roles, Manage Nicknames and Kick Members
(`INSTALL_PERMISSIONS`). Posting needs **Send Messages** and **Embed
Links**, and `@here` only notifies anyone with **Mention @everyone, @here
and All Roles**.

- New installs ask for these too.
- Already linked servers (M-EXC) grant them to the bot in the chosen
  channel, or reconnect the bot.
- The Settings tab checks the bot's permissions in the chosen channel and
  says what is missing ("can't post", "posts, but @here won't notify
  anyone"), like the invite status does today. A failed post (missing
  access, channel deleted) is shown there too.

## How it is built (approach chosen)

**Chosen: one shared "where does this group post go" step.** Every group
fleet post (roundup, pre-ping, start ping) asks one helper for its
destinations: the group's channel plus each following corporation's
channel, each with its own mention rule from the table above. The pre-ping
(`fleets/endpoints/helpers.py`) and the start ping
(`fleets/helpers/start_ping.py`, `EveFleet.notify_discord`) call it; a new
post type later gets forwarding the same way.

Not chosen:

- Adding a separate "also post to the corporation" step to each of the
  three posts: same work now, but three places to keep in sync.
- Discord's own Follow channel: needs an announcement channel instead of
  the chat channel, can't `@here`, and the site can't tell when it breaks.

Data (names are the builder's call):

- On the tribe group: roundup on/off and the roundup hour (whole EVE
  hours), set by anyone who can manage the group (`user_can_manage_group`)
  on the group's settings.
- New: a corporation's follow of a group: corporation, tribe group,
  channel id and name, status (requested, approved, revoked), who
  approved and when, last delivery status.
- A periodic task runs hourly and posts the roundup for each group whose
  hour has come. Discord posts go through the outbox
  (`discord/outbox.py`), never from a web request.

## Rule changes (docs/tribes/tribe-publishing.md)

- Rule 3 gains the roundup (silent, group's channel) and the forwarded
  copies (silent, start ping with `@here` in a corporation's server). Group
  fleets still never ping `@everyone`.
- Rule 2 says a members-only group item is never pinged outside the group.
  A corporation server is outside the group, so it gains an exception:
  "…or in a corporation's channel the group's chiefs approved"
  (decided 2026-11-27: the corporation asks, a chief approves).

## Non-goals

- Forwarding chat, reactions or other bot messages.
- Changing `#schedule` or alliance fleet pings (rule 1).
- Pinging a role in the corporation's server.

## Delivery

Concept first (this doc), then the build, one commit per part: the
roundup, the forwarding (backend), and the settings on the website.
