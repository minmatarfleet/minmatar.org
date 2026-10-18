# Tribe publishing: posts, fleets and events from tribe groups

Tribe groups can publish posts, schedule fleets and create Discord events
without changing any existing alliance flow. Wireframes:
https://claude.ai/artifact/CwnsJFFeCWWgaNVo53Zr8g

This file is the contract every part of the build follows. If code and this
file disagree, fix one of them in the same change.

## Rules that must hold (regression = breaking one of these)

1. A fleet or post with no `host_group` behaves exactly as before: same
   lists, same visibility, same Discord messages, same metrics, same
   `#schedule` message byte for byte.
2. A members-only group item is never shown, listed, counted in alliance
   metrics, pinged or scheduled outside the group. Its existence may be
   revealed (the gate page names the group), its content may not.
3. Group fleets never ping `@everyone` and never send a pre-ping. The only
   fleet ping is the start ping from `EveFleet.notify_discord`. The alliance
   does not do pre-pings: do not add any pre-ping UI or call
   `send_discord_pre_ping` for a group fleet.
4. "Open to the alliance" only makes a group fleet visible. Its ping still
   goes to the group's channel with the group's role.
5. Strategic fleets are alliance-only. A group fleet's type is
   non_strategic, training or npsi.

## Data model

### tribes.TribeGroup (new fields)

| field | type | default | meaning |
|---|---|---|---|
| `post_policy` | char `chiefs`/`chosen`/`members` | `chiefs` | who can post as the group |
| `fleet_policy` | same | `chiefs` | who can schedule group fleets |
| `event_policy` | same | `chiefs` | who can create group events |
| `post_publishers` | M2M User, blank | | chosen pilots for posts |
| `fleet_publishers` | M2M User, blank | | chosen pilots for fleets |
| `event_publishers` | M2M User, blank | | chosen pilots for events |
| `allow_alliance_posts` | bool | `True` | off: every group post is members only |
| `allow_open_fleets` | bool | `False` | publishers may open fleets to the alliance |

`discord_channel_id` already exists. The effective channel is
`group.discord_channel_id or group.tribe.discord_channel_id`.
The role mentioned is the group's auth group's `DiscordRole`
(`group.group.discord_group.role_id`), rendered `<@&role_id>`; its name is
the auth group name (e.g. `Tribe Group - Dreads`).

### fleets.EveFleet (new fields)

| field | type | default |
|---|---|---|
| `host_group` | FK TribeGroup, null, SET_NULL, related_name `hosted_fleets` | null |
| `open_to_alliance` | bool | False |
| `on_schedule` | bool | False |

A group fleet has `audience = None`.

### posts.EvePost (new fields)

| field | type | default |
|---|---|---|
| `host_group` | FK TribeGroup, null, SET_NULL, related_name `hosted_posts` | null |
| `members_only` | bool | False |
| `announced_at` | datetime, null | null |

`tribe_groups` (M2M, "Also show on groups") is unchanged.

### tribes.TribeEvent (new model, `tribes/models/tribe_event.py`)

`tribe_group` FK, `created_by` FK User (null), `title` (200),
`description` text, `starts_at`, `ends_at` (null), `recurrence`
(`none`/`weekly`/`monthly`, default `none`), `where_kind`
(`voice`/`place`), `voice_channel_id` bigint null, `voice_channel_name`,
`location` (200, blank), `members_only` bool, `announce` bool (default
True), `discord_event_id` bigint null, `interested_count` int (0),
`status` (`scheduled`/`cancelled`/`completed`, default `scheduled`),
`cancelled_at` null, `created_at`, `updated_at`.

`members_only` requires `where_kind == "voice"` (Discord shows location
events to the whole server). Monthly recurrence repeats on the same nth
weekday as `starts_at` (e.g. 2nd Saturday).

## Permissions (`tribes/helpers/publishing.py`)

- `is_active_member(user, group)`: active `TribeGroupMembership`.
- `can_publish(user, group, kind)` with kind `post`/`fleet`/`event`:
  `user_can_manage_group(user, group)` (superuser, chief, tribe chief,
  manage feature), or policy `members` and active member, or policy `chosen`
  and active member and in that kind's publishers.
- `publishable_groups(user, kind)`: active groups where `can_publish`.
- `visible_group_ids(user)`: groups the user is an active member of or can
  manage (all for superusers).
- Group fleet visibility: no host_group, or open_to_alliance, or
  host_group in `visible_group_ids`, or created_by user. Applied in
  `groups.helpers.feature_access.can_use_feature` for every fleet-scoped
  feature check (`fleet_hidden_from`, before the RESOURCE_MATCH scope and
  before the legacy-permission fallback, which would otherwise let
  `fleets.view_evefleet` holders through), so every single-fleet endpoint
  is covered, and as a queryset filter in every fleet list
  (`fleets.helpers.visibility.visible_fleets_q(user)`).
  Alliance metrics use `alliance_fleets_q()` (no host_group, or open).
- Group post visibility: not members_only, or host_group in
  `visible_group_ids`, or author.
- Editing a group post: its author, or anyone who can manage the group.

## API

`HostGroupRef` = `{id, code, name, tribe_id, tribe_name}`.

### Fleets

- `CreateEveFleetRequest` / `UpdateEveFleetRequest` gain
  `host_group_id: int | None`, `open_to_alliance: bool = False`,
  `on_schedule: bool = False`.
  - With `host_group_id`: needs `can_publish(..., "fleet")` (the
    `fleets.create` feature is not required); `audience_id` is ignored and
    stored as None; type `strategic` (or a campaign type) is a 400;
    `open_to_alliance` needs `group.allow_open_fleets` (400 otherwise);
    `on_schedule` is forced False unless open; `immediate_ping` is ignored.
  - On `UpdateEveFleetRequest` the three fields default to null and are
    only applied when sent, so a PATCH that leaves them out keeps the
    fleet's flags. A group fleet is edited by its FC, a Strategic FC or a
    manager of the group. `host_group_id: null` moves a group fleet back to
    an alliance audience (needs `audience_id` and `fleets.create`).
- `EveFleetResponse` (and the v3 list items) gain
  `host_group: HostGroupRef | None`, `open_to_alliance: bool`,
  `on_schedule: bool`.
- `GET /api/fleets/v3` returns group fleets the viewer can see, and takes an
  optional `host_group_id` to list one group's fleets.
- `GET /api/fleets/{id}` on a members-only group fleet the viewer can't see:
  `403 {detail: "members_only", host_group}` (`RestrictedResponse`). Other
  403s on this endpoint keep their `null` body.
- `POST /api/fleets/ping-preview` (`FleetPingPreviewRequest` = type,
  description, objective, location_id, audience_id, host_group_id) returns
  `FleetPingPreviewResponse` = `{channel_name, payload}`: the exact start
  ping payload, built by the same helper as `EveFleet.notify_discord`
  (`fleets.helpers.start_ping.build_start_ping`). `channel_name` is null
  when there is no channel. Needs `fleets.create`, or with
  `host_group_id` the group's fleet publishing right.
- Start ping for a group fleet: effective group channel, content = role
  mention, AUDIENCE line = group name. No channel → no ping.
- `#schedule`: alliance part unchanged. If there are upcoming group fleets
  with `open_to_alliance and on_schedule`, append:

  ```
  ### Tribe fleets
  - <emoji> 2026-10-27 23:30 EVE (<t:...>) Casper Sullivan · [Dreads](<group page url>) (Capitals) · Dread op
  -# Open to the alliance: message the FC or apply on the group's page.
  ```

  Omitted entirely when empty. The last part is the fleet's objective (or
  its doctrine name; left out when neither is set). Lines that would take
  the message past Discord's 2000 characters collapse into one
  `…and N more` line. Group page URL:
  `/alliance/tribes/<tribe_id>/<group_id>/`.
- Fleet metrics, FC metrics and results exclude group fleets that are not
  open to the alliance. So does every "fleets led" number
  (`fleets.helpers.metrics.led_fleets`) and the survey recent-fleets list.

### Posts

- `GET /api/blog/posts` and `GET /api/blog/posts/{id}` use optional auth and
  hide members-only posts the viewer can't see (detail: `403 {detail,
  host_group}`).
- `tribe_group_id` on the list returns posts hosted by the group or tagged
  with it.
- List and detail responses gain `host_group: HostGroupRef | None` and
  `members_only: bool`.
- Create/update requests gain `host_group_id: int | None`,
  `members_only: bool = False`, `announce: bool = False`. A group post needs
  `can_publish(..., "post")`; when the group has
  `allow_alliance_posts = False` the post is stored members only. When a
  group post is first published with `announce`, the bot posts the title and
  link in the group's channel with the role mention (once; `announced_at`).

### Tribe groups

- `TribeGroupSchema` gains viewer flags `is_member`, `can_post`,
  `can_schedule_fleets`, `can_create_events`, and `allow_alliance_posts`,
  `allow_open_fleets`, `effective_discord_channel_id`, `discord_role_name`.
- `GET /api/tribes/groups/{group_id}/publishing` (managers):
  `TribeGroupPublishingSchema` = policies, publisher lists
  (`[{character_id, character_name}]`), the two allow flags,
  `discord_channel_id`, `effective_discord_channel_id`,
  `effective_discord_channel_name`, `discord_role_name`.
- `PATCH` same path with `TribeGroupPublishingPatch` (all optional):
  policies, `*_publisher_character_ids`, allow flags, `discord_channel_id`.
- `GET /api/tribes/publishable-groups?kind=post|fleet|event`:
  `[PublishableGroupSchema]` = HostGroupRef + `member_count`,
  `allow_alliance_posts`, `allow_open_fleets`.
- `GET /api/tribes/discord-channels?kind=text|voice` (anyone who can
  manage a group or publish events for one): `[{id, name, type}]`, voice
  includes stage channels, cached 10 minutes.

### Events

- `GET /api/tribes/groups/{group_id}/events`: upcoming events plus ones
  cancelled in the last 24 hours, members-only filtered by visibility.
- `POST /api/tribes/groups/{group_id}/events` (`can_publish event`):
  `TribeEventCreate` = title, description, starts_at, ends_at,
  recurrence, where_kind, voice_channel_id, location, members_only,
  announce.
- `PATCH /api/tribes/events/{event_id}` and
  `POST /api/tribes/events/{event_id}/cancel`: creator or group manager.
- `TribeEventSchema`: all fields above plus `tribe_group: HostGroupRef`,
  `discord_event_url` (`https://discord.com/events/<guild>/<id>` or null),
  `can_manage`.
- Discord: the bot creates a guild scheduled event (privacy GUILD_ONLY;
  stage channel → entity_type 1, voice → 2, place → 3 with
  `entity_metadata.location` and a required end time; recurrence via
  `recurrence_rule`). Description starts `Hosted by <group>.` Create, edit
  and cancel go through Celery tasks after commit. A periodic task reads
  `user_count` back into `interested_count`. Announcement in the group
  channel: role mention, one line, the event link. The bot needs the
  Manage Events permission.

## Launch data migrations (Discord is the source of truth)

1. The audience on channel `1064548000397021224` named `#warzone-pings` is
   renamed `#pings`.
2. Groups with no `discord_channel_id` are linked to their channel in the
   Tribes category, matched by the slug after the tribe prefix (supply.*,
   the older industry.*, or pulse.*: technology, readiness, thinkspeak and
   fleet-commanders are `pulse.` groups):
   mining 1450351308027592715, freighters 1465125012901203983, market
   1490366732458528981, planetary-interaction 1480262027485380659,
   technology 1174095095537078312, readiness 1391028680934822018,
   thinkspeak 1172908092573360149, fleet-commanders 1475181633232437408.
   `#production` is not linked: it is unclear whether it belongs to
   subcapital or capital production. Capitals groups keep the `#capitals`
   tribe fallback.

## Website

Group page `/alliance/tribes/<tribe_id>/<group_id>/`, tab order: About,
Requirements, Guides, Activity, Members, Fleets, Events, Posts (was
Propaganda; `#propaganda` aliases to `#posts`), Settings (managers only).
A tab shows only when it has something or the viewer can add to it.
A "New" menu (post, fleet, event) shows for anyone with a `can_*` flag.

| Page | URL |
|---|---|
| Post editor | `/alliance/propaganda/new/editor?host=<group_id>` |
| Fleet form | `/fleets/add/?host=<group_id>` |
| Event form | `/alliance/tribes/<t>/<g>/events/new` |
| Event edit | `/alliance/tribes/<t>/<g>/events/<id>/edit` |
| Fleet history for a group | `/fleets/history/?group=<group_id>` |

Components (frontend/app/src/components/blocks/): `TribeGroupChip`,
`VisibilityTag`, `HostPicker`, `PostTile`, `MembersOnlyGate`,
`TribeEventRow`, `EventWherePicker`, `DiscordEmbedPreview` (+
`partials/discord_preview_component.astro`). Extended: `Tag` (outline
variant), `SectionTabs` (scrolls at every width), `FleetScheduleRow`,
`FleetSpotlight`, `FleetHistoryRow`, `FleetHero` (host strip),
`FleetFeedItem`, `FleetForm`, the post editor, `PostItem`, desktop
`render_fleet`.
