# Group fleets for associate members: seeing and pinging Mining fleets

**Status:** concept, nothing built yet. This doc explains why M-EXC miners in the
Mining group can't see or ping Mining fleets. It proposes opening the Fleets
pages to the whole community and letting **each fleet** decide who sees it,
which fixes this for every tribe group, not just Mining. Read the
[production check](#production-check) before building: it confirms which of the
blockers below apply today.

## The report

Pilots of Minmatar Extraction Company (M-EXC) are active members of the Mining
tribe group (`/alliance/tribes/2/6/`). M-EXC is corporation `98838663`, the
buyback corporation (`BUYBACK_CORPORATION_ID` in `backend/buyback/models.py`).
The Mining chief reports:

1. M-EXC members **don't see the Fleets tab** on the website at all, so they
   can neither see upcoming fleets nor create one.
2. A Mining fleet was created, but it **didn't ping the Mining role** in the
   Mining channel, although the form says it will.
3. The fleet didn't appear in the Discord fleet schedule. That part is
   intended: it was a group fleet, not open to the alliance.

## Why: M-EXC pilots are associates

M-EXC is a corporation in **Minmatar Fleet Associates** (ticker BUILD, alliance
`99012009`, `MINMATAR_FLEET_ASSOCIATES_ALLIANCE_ID` in
`backend/eveonline/constants.py`). A pilot whose main is in M-EXC gets the
**Associate** affiliation, not Alliance.

The site's fleet permissions are alliance-wide features decided by affiliation
(`backend/groups/features/registry.py`):

| Feature | Default affiliations | Gates |
| --- | --- | --- |
| `fleets.view` | Alliance, Militia, Associate | the Fleets entry in the Neocom, `/fleets/*` pages, the fleet list (`GET /api/fleets/v3`), a fleet's page, and the group page's Fleets tab |
| `fleets.create` | **Alliance only** | creating alliance fleets, `/fleets/start/`, the flash form, and the form's reference data: `GET /api/fleets/audiences`, `GET /api/fleets/v2/locations`, `GET /api/fleets/types` |

Each feature has exactly one scope (`_evaluate_scope` in
`backend/groups/helpers/feature_access.py`). `fleets.view` is resource-match
(affiliation plus the fleet's audience), and `fleets.create` is affiliation.
Neither scope looks at tribe group membership. `can_use_feature` also accepts
each feature's old Django permission (`fleets.view_evefleet`,
`fleets.add_evefleet`), so an auth group holding that permission gets the
feature, but there's no way to say "the Mining group's members" in either
feature.

Tribe groups already have their own fleet rights, separate from these
features (`backend/tribes/helpers/publishing.py`):

- **Scheduling** is `can_publish(user, group, "fleet")`, and the groups a
  pilot may host for are `publishable_groups(user, "fleet")`: the group is active,
  `fleets_enabled` is on, and the pilot manages the group or the group's
  `fleet_policy` allows them (chiefs, chosen pilots, or any active member).
  `POST /api/fleets` and `POST /api/fleets/ping-preview` already skip
  `fleets.create` when the fleet has a `host_group_id`.
- **Seeing a members-only group fleet** is `fleet_visible_to`: the creator,
  active members and managers.

So the group's rules are half wired in. They replace `fleets.create` when the
fleet is submitted, but the pages and reference data around that call still
ask for the alliance-wide features.

## The blockers, in the order an associate hits them

| # | Step | What decides it today | Effect on an Associate group member |
| --- | --- | --- | --- |
| 1 | See the Fleets entry and `/fleets/upcoming/` | `fleets.view` as a **page gate** | Allowed **by default**. The report says it isn't, so production differs: `fleets.view` isn't wired to Associate, or the pilots don't have the Associate affiliation (no main character set, for example). The production check shows which. |
| 2 | See the group's fleets on its page and open a fleet | `fleets.view` again as a page gate, then per fleet in `GET /api/fleets/v3` and `GET /api/fleets/{id}` | Same as 1. Being an active member of the group doesn't count at the page gate, though the per-fleet checks already let members see their group's fleets. |
| 3 | Open the fleet form for the group (`/fleets/add/?host=6`) | Page: `fleets.create` **or** a publishable group (already group-aware). Reference data: `fleets.create` only. | The page opens, but `get_audiences` and `get_locations` return 403, so the form fails to load. **A code bug even when the policy allows the pilot.** |
| 4 | Schedule as the group | `can_publish` (`fleet_policy`) | Works once the Mining chief allows members (see [the earlier settings check](#settings-the-mining-chief-controls)). |
| 5 | Start the fleet, which sends the ping | `POST /api/fleets/{id}/tracking`: the fleet's creator only. Reaching the button needs the fleet page (blocker 2). `/fleets/start/` and "start now" need `fleets.create`. | Blocked by 2, and by `fleets.create` for start-now. |
| 6 | The ping itself | `EveFleet.notify_discord` → `build_start_ping` | Goes to the group's channel (or the tribe's), mentioning the group's Discord role. **No channel means no ping, and no linked Discord role means a ping with no @ mention.** |

### Why the reported fleet didn't ping

A group fleet has **one** Discord ping: the start ping, sent when its creator
starts it on the site, which creates the in-game fleet
(`docs/tribes/tribe-publishing.md` rule 3). Scheduling a group fleet never
pings, by design. The fleet didn't ping for one of these reasons, which the
production check tells apart:

- it was never started on the site (formed in game instead), so there was no
  start ping;
- the Mining group and its tribe have no Discord channel set;
- the group's auth group has no linked Discord role, so the ping went out with
  no mention.

If the form's wording made the chief expect a ping at scheduling time, the form
copy is wrong and should say "pings the Mining role when you start the fleet".

## Proposal: the Fleets pages are open, each fleet decides who sees it

> **Rule.** Every pilot with the Alliance, Militia or Associate affiliation can
> open the Fleets pages. Guests can't; they keep only the public kills page. Which fleets a pilot sees
> there is decided **per fleet** by the API: its audience, its host group, and
> whether it's private. The page gate stops being the thing that hides fleets.

This needs no new feature and no second set of gates. Most of it exists:

- **Per-fleet filtering:** `visible_fleets_q` (`backend/fleets/helpers/visibility.py`)
  already hides members-only group fleets and private fleets from pilots who
  can't see them, and lets group members, managers and the creator see them.
- **Public history:** `public_kills_allowed` already lets anyone with the link
  open a fleet's kills page (`GET /api/fleets/{id}/public-kills`,
  `/fleets/{id}/kills`). Members-only group fleets, hidden audiences and
  cancelled fleets are left out.
- **Rosters:** hidden by default (`EveFleet.hide_volunteers`, default on). Only
  the fleet's FC and Strategic FCs see every name (`sees_all_volunteers`).

### What each viewer sees

| Viewer | Upcoming fleets | Finished fleets and history |
| --- | --- | --- |
| Public, signed out | none | type, result, kills and losses, ship classes, battle report (killmails are public on zKill anyway) |
| Community member | fleets they're allowed to see: matching audience, their groups' fleets, private fleets they're invited to | as above, plus their own participation |
| Group member, FC, manager | as above, plus members-only group fleets | rosters and participants, where the roster settings allow |

Names, full rosters and FC time patterns stay behind membership. Upcoming
fleets and form-up times stay behind sign-in.

### 1. Needed before the pages open: the list filters by audience (backend)

`GET /api/fleets/v3` (`backend/fleets/endpoints/catalog/get_v3_fleets.py`)
doesn't check a fleet's **audience groups**. It drops hidden audiences,
members-only group fleets and private fleets, nothing else. The fleet detail
endpoint does run the audience-group check, through `fleets.view` with the
fleet (`_evaluate_resource_match`: a fleet whose audience lists auth groups is
visible only to pilots in one of them, or whose affiliation's group is listed).

Today that gap is covered by who can reach the page. Once Associates can open the page,
an Alliance-only fleet would show up in an associate's list. So:

- Add the audience-group condition to the list as a queryset filter (next to
  `visible_fleets_q`): no audience or an audience with no groups, **or** an
  audience group the pilot is in, **or** the group of the pilot's affiliation.
  Group fleets have no audience and keep following `visible_fleets_q`.
  Strategic FCs and superusers still see everything.
- One helper decides both the list and the detail, so they can't drift. A test
  proves a fleet hidden from a pilot by the detail endpoint is also missing from
  their list.
- The list still needs `fleets.view`, as today. Alliance, Militia and
  Associate pilots all have it, and the Fleets pages open only to them.

### 2. Opening the pages (website)

- The Neocom Fleets entry, `/fleets/upcoming/`, `/fleets/history/`, a fleet's
  page (`/fleets/upcoming/{id}`, `/fleets/history/{id}` and its report), and the
  partials behind them keep `fleets.view` only as "is this pilot Alliance,
  Militia or Associate", which is its default affiliation list. They no longer
  hide fleets; they show whatever the API answers.
- A fleet the API refuses renders as not found or forbidden, as today. The
  per-fleet checks on the API (`_fleet_authorized`, `visible_fleets_q`,
  `sees_all_volunteers`) stay as they are.
- The group page's Fleets tab (`[group_id].astro`) shows for the same pilots
  and lists what the API answers for that group.
- Signed-out visitors keep the public kills page, which already works. Opening
  fleet history and the battle report to them is a later step: `GET
  /api/fleets/v3` requires sign-in today, so it needs a public mode that never
  returns upcoming fleets, names or rosters.

### 3. Scheduling and starting (backend)

- `GET /api/fleets/v2/locations` and `GET /api/fleets/types`: allow
  `fleets.create` **or** "can publish fleets for some group"
  (`publishable_groups(user, "fleet")` is non-empty). Fleet types are already
  limited to `GROUP_FLEET_TYPES` when the fleet has a host group.
- `GET /api/fleets/audiences` stays `fleets.create` only. A group fleet has no
  audience, so `add.astro` must stop requiring it when the pilot can only host
  as a group (send `[]`, don't fail the form).
- `POST /api/fleets/{id}/tracking` (start) stays creator-only. It needs no
  change once the creator can reach the fleet's page, which §2 opens.
- Start-now (`/fleets/start/`, the flash form, `POST /api/fleets/start-now`):
  for a group fleet, `can_publish` instead of `fleets.create`, as for
  scheduling. This can be a second step: scheduling for "now" and pressing
  Start works without it.

### 4. The ping (settings plus one copy fix)

- No code change to `build_start_ping`. The group needs a Discord channel
  (group or tribe) and a linked Discord role. Both are settings, checked in the
  production check.
- The form's ping preview already shows the group's channel. When the preview
  has no channel or no role mention, show that plainly ("This fleet won't
  ping: the group has no Discord channel"), so the chief finds out before the
  fleet, not after.
- Copy: say the ping goes out **when the fleet is started**, not when it's
  scheduled.

### Settings the Mining chief controls

Who may schedule and ping Mining fleets is the Mining chief's decision, made in
the group's settings; this concept doesn't choose it. These were the original
analysis and still apply. Scheduling as the group is
per pilot (`can_publish`), and the corporation plays no part:

1. `fleets_enabled` on (default on).
2. "Schedule Mining fleets" (`fleet_policy`) set to **Any active member**, or
   **Chiefs and chosen pilots** with the miners who run fleets listed. The
   default is **Chiefs only** (migration `0043_tribe_publishing`) and was never
   changed for existing groups, so members are blocked until a chief changes
   it.
3. The pilots' memberships are **active**, not pending or inactive.

### Alternatives considered

- **Give Associates `fleets.create` in the admin.** No code, but every
  associate could then schedule alliance fleets with an `@everyone` ping. Too
  broad, and it ignores the group's own policy.
- **A new `fleets.view_group` feature (tribe-membership scope) and gate.** The
  first draft of this concept. It adds a second set of gates next to
  `fleets.view` while the API already decides visibility per fleet, and a
  tribe-membership feature with no tribe groups listed denies everyone
  (`_evaluate_tribe_membership`), so it would need every fleet-hosting group
  listed in the admin.
- **Wire `fleets.view`/`fleets.create` to the Mining group.** Not possible:
  a feature has one scope and these two aren't tribe-membership features.
  Changing their scope would change who sees alliance fleets.
- **A corporation rule for M-EXC.** It would bypass the group's chiefs and not
  help associates from other corporations, or other groups.
- **Do nothing and tell M-EXC to join the alliance.** M-EXC is in the
  associates alliance on purpose (industry and buyback), so this isn't a fix.

### What this doesn't change

- Alliance fleets, their `@everyone` pings, and the Discord fleet schedule.
- Members-only group fleets stay hidden from everyone outside the group
  (tribe-publishing rule 1).
- Group fleets still never pre-ping (rule 3).
- No desktop-facing payload changes. `GET /api/fleets/v3` keeps its shape. It
  leaves out fleets whose audience the pilot isn't in, which the detail
  endpoint already refuses them. It's on the desktop's list (`.claude/rules/desktop-release.md`), and no
  field changes.

## Production check

Read-only. It prints the fleet features' affiliations, the Mining group's
settings, its Discord channel and role mention, its last five fleets (and
whether each was started on the site), then one line per M-EXC pilot: main
character, affiliation, community status, membership, `fleets.view`,
`fleets.create`, and whether they can schedule as the group.

```bash
docker compose -f docker-compose-prod.yml exec app python3 manage.py shell -c 'from groups.models import PilotFeature as PF; [print("FEATURE", p.code, "affiliations", sorted(p.affiliations.values_list("group__name", flat=True)), "deny", p.deny_community_statuses) for p in PF.objects.filter(code__in=["fleets.view","fleets.create"])]; from tribes.models import TribeGroup as G, TribeGroupMembership as M; from tribes.helpers.publishing import can_publish, group_role_mention; from groups.helpers.feature_access import can_use_feature as F, user_affiliation as UA, user_community_status as US; from eveonline.models import EveCharacter as C; from eveonline.helpers.characters import user_primary_character as P; from fleets.models import EveFleet as EF, EveFleetInstance as EI; from django.contrib.auth.models import User; g=G.objects.select_related("tribe").filter(pk=6).first(); print("GROUP", g and (g.name, "fleets_enabled", g.fleets_enabled, "policy", g.fleet_policy, "group_channel", g.discord_channel_id, "tribe_channel", g.tribe.discord_channel_id, "role_mention", repr(group_role_mention(g)))); [print("FLEET", f.id, f.start_time, f.status, "by", f.created_by and f.created_by.username, "open", f.open_to_alliance, "on_schedule", f.on_schedule, "started_on_site", EI.objects.filter(eve_fleet=f).exists()) for f in EF.objects.filter(host_group_id=6).order_by("-start_time")[:5]]; users=User.objects.filter(pk__in=C.objects.filter(corporation_id=98838663, user__isnull=False).values("user_id")); [print(u.username, "| main", (lambda p: p and (p.character_name, p.corporation_id, p.alliance_id))(P(u)), "| affiliation", (lambda a: a and a.name)(UA(u)), "| status", US(u), "| membership", M.objects.filter(user=u, tribe_group_id=6).values_list("status", flat=True).first(), "| fleets.view", F(u, "fleets.view"), "| fleets.create", F(u, "fleets.create"), "| can_schedule_group", g and can_publish(u, g, "fleet")) for u in users]'
```

| Output | Means | Fix |
| --- | --- | --- |
| `FEATURE fleets.view` without `Associate` | blocker 1 is a setting | Add Associate in the admin (Pilot features) today. Once the pages are open, the page no longer asks. |
| A pilot with `affiliation None` | no main character or no matching affiliation | The pilot sets a main; check the Associate affiliation lists alliance `99012009`. |
| `status on_leave` | the fleet features deny on-leave pilots | Expected. |
| `policy chiefs`, or `chosen` without the pilot | blocker 4 | The Mining chief changes the policy. |
| `group_channel None` and `tribe_channel None` | no ping possible | Set the group's Discord channel. |
| `role_mention ''` | ping without a mention | Link the Mining auth group to its Discord role. |
| `FLEET … started_on_site False` | the fleet was never started on the site, so no ping | Start group fleets from the fleet page. |

## Delivery

Small PRs, one layer at a time:

1. **This concept** (docs only).
2. **Backend:** the audience-group filter on `GET /api/fleets/v3`, shared with
   the detail check; locations and types for group publishers. Tests: an
   Associate active member sees their group's fleets; a non-member Associate doesn't see members-only group fleets
   or an Alliance-only audience fleet, in the list or the detail; an on-leave
   member. Regenerate the OpenAPI schema and contracts.
3. **Website:** open the Fleets pages, partials, history and the group Fleets
   tab to Alliance, Militia and Associate pilots; the form without audiences for group-only hosts;
   the ping-preview warning and copy. This must ship **after** 2, or the list
   leaks audience fleets.
4. **Later:** public, signed-out fleet history and battle reports; start-now
   for group fleets.

## Decisions

1. **Who opens the Fleets pages:** Alliance, Militia and Associate. Guests don't.
2. **Mining's fleet policy:** set by the Mining chief, who decides who may
   schedule and ping Mining fleets.

## Open questions

1. What does the production check show? It decides whether blocker 1 is a
   setting to fix today, before the pages open.
