# Pilot timezones and timezone roles

Every pilot gets a home timezone and a set of **brackets**: the times of day they are usually around. The brackets become Discord roles (`USTZ`, `USTZ+`, `EUTZ`, `EUTZ+`, `AUTZ`, `AUTZ+`), so FCs and channels can ping the people who will actually be online.

The `timezones` app owns this. `PilotTimezone` is the one place to read a pilot's timezone from, declared or inferred. Other features should read it through `timezones.services`, not work it out again.

## Brackets

Each region's brackets are fixed in that region's own clock: **after work** is 18:00–23:00, and **+** is the late side of the same evening, 23:00–03:00. Daylight saving moves them in EVE time, never in local time.

| Bracket | Local | EVE time, April–October | EVE time, November–March |
| --- | --- | --- | --- |
| USTZ | 18:00–23:00 Eastern | 22:00–03:00 | 23:00–04:00 |
| USTZ+ | 23:00–03:00 Eastern | 03:00–07:00 | 04:00–08:00 |
| EUTZ | 18:00–23:00 Central European | 16:00–21:00 | 17:00–22:00 |
| EUTZ+ | 23:00–03:00 Central European | 21:00–01:00 | 22:00–02:00 |
| AUTZ | 18:00–23:00 Sydney | 08:00–13:00 | 07:00–12:00 |
| AUTZ+ | 23:00–03:00 Sydney | 13:00–17:00 | 12:00–16:00 |

Each region changes its clocks on its own dates, so for a week or two in spring and autumn the brackets sit an hour off this table. The UK runs an hour behind the EU brackets. Pacific pilots' evenings run from late USTZ into USTZ+. A crossover fleet around 22:00–02:00 EVE time pings USTZ and EUTZ+ together.

## How a pilot is assessed

Activity over the last 90 days, from `timezones.activity`:

- one event per fleet joined;
- one event per killmail, as attacker or victim, from the pilot's ESI killmails and the zKillboard feed, counted once;
- one event per clock hour with voice in a tracked channel.

Alts fold into their owner. Text messages are not recorded anywhere, so they are not a source.

`timezones.inference.assess` then gives the pilot:

1. **A home timezone.** A model of when US and EU pilots play, on each region's own clock, says which evening the pilot's activity looks like. AU is home when a pilot plays more AU evenings than US or EU ones, because there are too few known AU pilots to model.
2. **The home's base bracket**, always.
3. **The home's + bracket**, when they are regularly on late.
4. **Another region's base bracket**, for each other region whose evening they regularly play. A US pilot who flies EU fleets in their afternoon gets EUTZ as well as USTZ.

**Regularly** means at least 4 distinct evenings, and at least 15% of their active days. A bracket already held stays until the pilot drops below 2 evenings or 8%, so pilots near the line don't gain and lose it every run.

Time inside a pilot's own evening never counts toward another region. An EU pilot on at 01:00 EVE time is up late (EUTZ+), not playing US prime.

### Declared prime time

`EvePlayer.prime_time` is the starting point. It is set on the profile, or parsed from a corporation application. It also tilts the home model, and it wins whenever the model is less than 80% sure, which includes pilots with no activity yet.

The application form turns "region + time of day" into a code, so the crossover codes mean the opposite of their labels:

| Declared | Means | Applicants with a known location |
| --- | --- | --- |
| `EU_US` ("EUTZ – USTZ") | US | 12 of 12 US |
| `US_AP` ("USTZ – AUTZ") | EU | 3 of 3 EU |
| `AP_EU` ("AUTZ – EUTZ") | EU | 11 EU, 4 US |

### Accuracy

The application form also records the browser's IANA timezone. That is the ground truth: 182 members with a known US or EU location, as of October 2026.

- From activity alone, the model gets the home region right 80–83% of the time.
- With the declared prime time, it gets 82–85% right.
- When it is at least 80% sure, it is right about 89% of the time.

The misses are mostly US pilots who only fly EU-time fleets in their afternoon, so their own evening never shows up. Even so, they get EUTZ, which is when they are on.

`manage.py check_timezones` re-scores the model against the current applicants. It also prints fresh `HOME_PROFILES` to paste into `timezones.inference` when the alliance's schedule moves.

## Reading timezones

```python
from timezones.services import (
    timezone_for,
    timezone_tags_for,
    timezones_for,
    users_in_bracket,
)

row = timezone_for(user.id)  # PilotTimezone or None
row.home, row.home_source, row.brackets
row.declared_prime_time, row.declared_home  # what they said
row.inferred_home, row.inferred_confidence  # what activity says

users_in_bracket("EUTZ+")  # eligible pilots holding a bracket
timezone_tags_for(user_ids)  # user id -> TimezoneTag, for pages
```

`eligible` is true for active and trial members with Discord linked. On-leave pilots keep a timezone but hold no roles.

Pages show a pilot's timezone as a `TimezoneTag` (`timezones.schemas`): `brackets` and `source` (`"activity"` or `"declared"`; no brackets means nothing is known yet). Build them in one query with `timezone_tags_for(user_ids)`, and render them with the website's `TimezoneTags` component: solid tags from activity, dashed when only declared, "No TZ yet", or "On Leave" in its place where leave matters.

## Where pilots' timezones show

Every one of these reads `PilotTimezone`; none reads `EvePlayer.prime_time` or guesses from fleet attendance itself.

| Surface | Field | Notes |
| --- | --- | --- |
| Corporation page, Leadership | `leadership[].timezone` on `CorporationResponse` / `CorporationInfoResponse` | On Leave (community status) replaces the tags. The CEO and recruiter zone pills are the tag's regions (US, EU, AU). Read live, not from the cached profile stats. |
| Corporation page, About | `about.prime_windows[].pilots` | Members holding a bracket in that window's region. The windows themselves come from the corp's own free-text timezones. |
| Corporation Members roster | `CorporationMemberDetails.timezone` | Filter by USTZ, EUTZ or AUTZ (each takes in its + bracket) or No TZ yet; the timezone sort is bracket order. |
| Alliance Health pilot cards | `timezone` on attention, trial and leave pilots | Sorts in bracket order; search matches bracket codes. |
| Campaign roster | `RosterRow.timezone`, `Roster.by_timezone` | "Pilots by timezone": one count per bracket, then No TZ yet. |
| Survey context card | `MemberContextSchema.timezone`, `timezone_note` | The note is the pilot's home region's share of eligible pilots (`home_counts()`). Survey responses still freeze the declared `prime_time` for segmentation, so past quarters stay comparable. |

Not pilot timezones, and left alone: a fleet's `time_region` (when the fleet ran), and a corporation's own declared timezones text.

To react to changes, connect to `timezones.services.pilot_timezone_changed`. It is sent with `instance`, `previous_home`, `previous_brackets` and `previous_eligible` whenever a pilot's home, brackets or eligibility change.

## When it runs

- `timezones.tasks.assess_timezones` every 6 hours reassesses everyone, then reconciles Discord roles.
- Saving a new declared prime time queues `assess_user_timezone` for that pilot, so the change takes effect straight away. That includes the prime time parsed from a corporation application's "Timezone:" line.
- **Sync with Discord** on the account page applies the pilot's stored brackets (`users/router.py`).
- `manage.py assess_timezones [--user ID] [--dry-run]` runs an assessment by hand.

## Discord roles

Each bracket is an auth group (`TimezoneRole`) named after its code. The usual group-to-role sync in `discord.signals` carries membership to Discord, fail-closed (see [auth/discord-groups.md](auth/discord-groups.md)). `timezones.discord_roles.apply_roles` is a desired-state reconciler: a refused add or remove is logged and retried on the next run.

The first run after deploy creates the six groups, which creates their Discord roles, and assigns them to every eligible pilot: about 1,100 role adds, which take a few minutes behind the Discord client's rate limiting. To preview it first, run `manage.py assess_timezones --dry-run`; it saves nothing and touches no roles.

A group adopts an existing Discord role with the same name instead of creating one. The reconciler then owns that role and removes it from anyone who doesn't qualify.

## Code map

| Piece | Path |
| --- | --- |
| Brackets and their clocks | `backend/timezones/brackets.py` |
| Activity sources | `backend/timezones/activity.py` |
| Home model and bracket rules | `backend/timezones/inference.py` |
| Storage, readers, change signal | `backend/timezones/services.py` |
| Page schema (`TimezoneTag`) | `backend/timezones/schemas.py` |
| Website tag and helpers | `frontend/app/src/components/blocks/TimezoneTags.astro`, `frontend/app/src/helpers/timezones.ts` |
| Discord role reconciler | `backend/timezones/discord_roles.py` |
| Tasks | `backend/timezones/tasks.py` |
| Declared prime time hook | `backend/timezones/signals.py` |
