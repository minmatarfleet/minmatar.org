# Group fleets for associate members: seeing and pinging Mining fleets

**Status:** concept, nothing built yet. This doc explains why M-EXC miners in the
Mining group can't see or ping Mining fleets, and proposes a permission rule
that fixes it for every tribe group, not just Mining. Read the
[production check](#production-check) before building: it confirms which of the
blockers below apply today.

## The report

Pilots of Minmatar Extraction Company (M-EXC) are active members of the Mining
tribe group (`/alliance/tribes/2/6/`). The Mining chief reports:

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
Neither can also be granted to a tribe group's members, so the Mining group
can't be added to them through the admin.

Tribe groups already have their own fleet rights, separate from these
features (`backend/tribes/helpers/publishing.py`):

- **Scheduling** is `can_publish(user, group, "fleet")`: the group is active,
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
| 1 | See the Fleets entry and `/fleets/upcoming/` | `fleets.view` | Allowed **by default**. The report says it isn't, so production differs: `fleets.view` isn't wired to Associate, or the pilots don't have the Associate affiliation (no main character set, for example). The production check shows which. |
| 2 | See the group's fleets on its page and open a fleet | `fleets.view` (page gate, `GET /api/fleets/v3`, `GET /api/fleets/{id}`) | Same as 1. Being an active member of the group doesn't count. |
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

## Proposal: a group fleet follows the group's rules

> **Rule.** For a fleet hosted by a tribe group, the group's own rights decide
> who may see, schedule, and start it. The alliance-wide `fleets.view` and
> `fleets.create` features decide alliance fleets, and the fleet pages a pilot
> can only reach through them.

The repo already follows this rule when a group fleet is created. The proposal
applies it to the rest of the flow. It doesn't widen any alliance permission:
an associate gets nothing outside the groups whose chiefs let them in.

### 1. Seeing group fleets (backend)

- `GET /api/fleets/{id}` and the volunteer/role endpoints (`_fleet_authorized`
  in `backend/fleets/endpoints/helpers.py`): also allow a group fleet when
  `fleet_visible_to(user, fleet)` is true for a reason other than "open to the
  alliance", that is, creator, active member, or manager.
  An open group fleet keeps needing `fleets.view` for outsiders, as today.
- `GET /api/fleets/v3`: without `fleets.view`, answer only the group fleets the
  pilot can see through their memberships (`visible_fleets_q` restricted to
  `host_group` in the pilot's groups) instead of 403. With `fleets.view`,
  nothing changes.
- A new pilot feature **`fleets.view_group`**, scope `tribe_membership`, meaning
  "an active member, or a manager, of at least one active group with
  `fleets_enabled`". It needs no tribe group list: any such group counts.
  It's what the website gates on, so gates still map to pilot features
  (`docs/auth/frontend-feature-gating.md`). On-leave pilots are denied, like the
  other fleet features.

### 2. Seeing group fleets (website)

- A gate `fleets.view_group` in `frontend/app/src/json/feature_gates.json`.
- The Neocom Fleets entry, `/fleets/upcoming/` and a fleet's page show for
  `fleets.view` **or** `fleets.view_group`. Without `fleets.view` the list is
  whatever the API answers, so only that pilot's group fleets.
- The group page's Fleets tab (`[group_id].astro`) shows for `fleets.view` or
  for an active member or manager of that group (the group response already
  says which).

### 3. Scheduling and starting (backend)

- `GET /api/fleets/v2/locations` and `GET /api/fleets/types`: allow
  `fleets.create` **or** "can publish fleets for some group" (the same list
  `get_publishable_groups(user, "fleet")` answers). Fleet types are already
  limited to `GROUP_FLEET_TYPES` when the fleet has a host group.
- `GET /api/fleets/audiences` stays `fleets.create` only. A group fleet has no
  audience, so `add.astro` must stop requiring it when the pilot can only host
  as a group (send `[]`, don't fail the form).
- `POST /api/fleets/{id}/tracking` (start) stays creator-only. It needs no
  change once the creator can reach the fleet's page.
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

These were the original analysis and still apply. Scheduling as the group is
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
- No desktop-facing payload changes. `GET /api/fleets/v3` keeps its shape and
  answers more pilots. It's on the desktop's list
  (`.claude/rules/desktop-release.md`), so the change stays additive.

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
| `FEATURE fleets.view` without `Associate` | blocker 1 is a setting | Add Associate in the admin (Pilot features), or rely on `fleets.view_group` once built. |
| A pilot with `affiliation None` | no main character or no matching affiliation | The pilot sets a main; check the Associate affiliation lists alliance `99012009`. |
| `status on_leave` | the fleet features deny on-leave pilots | Expected. |
| `policy chiefs`, or `chosen` without the pilot | blocker 4 | The Mining chief changes the policy. |
| `group_channel None` and `tribe_channel None` | no ping possible | Set the group's Discord channel. |
| `role_mention ''` | ping without a mention | Link the Mining auth group to its Discord role. |
| `FLEET … started_on_site False` | the fleet was never started on the site, so no ping | Start group fleets from the fleet page. |

## Delivery

Small PRs, one layer at a time:

1. **This concept** (docs only).
2. **Backend:** `fleets.view_group` feature, group-aware fleet detail, list,
   locations and types, with tests for an Associate active member, a
   non-member Associate (still blocked from members-only fleets), and an
   on-leave member. Regenerate the OpenAPI schema and contracts.
3. **Website:** the gate, Neocom/upcoming/fleet page/group Fleets tab, the
   form without audiences for group-only hosts, and the ping-preview warning
   and copy.
4. **Optional:** start-now for group fleets.

## Open questions

1. What does the production check show? It decides whether blocker 1 is a
   setting to fix today or only fixed by `fleets.view_group`.
2. Should `fleets.view_group` let a member see **all** upcoming alliance fleets,
   or only their groups' fleets (as proposed)? Only their groups' fleets keeps
   associates' access unchanged outside the groups they're in.
3. Should Mining's fleet policy be "Any active member" or "Chiefs and chosen
   pilots"? This is the Mining chief's call.
