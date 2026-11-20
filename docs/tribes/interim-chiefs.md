# Interim chiefs and chief volunteers

A tribe or group with no chief still shows a chief: whoever stands in. The
page then says **Help wanted**, and pilots can volunteer. The alliance
executor gets a Discord DM and appoints someone, or says not now.
Wireframes: https://claude.ai/artifact/4KNNTmH9Q8LS3hMWwxKF7z

## Timezone seats

A tribe has one chief. A **tribe group** has up to three, one per timezone
seat: **USTZ**, **EUTZ** and **AUTZ** (`tribes.TribeGroupChief`, region `US`,
`EU`, `AU`; one pilot per seat, one seat per pilot). It works like a
corporation's directors spread across timezones: every seated chief leads
the group.

- Every seated chief manages the group (`user_can_manage_group`) and uses the
  tribe-chief features wired to it, such as `freight.manage` for the
  Freighters group.
- Every seated chief is pinged: new applications, the pending-application
  reminder, help tickets, and external-guild alerts.
- Every seated chief is in the `Tribe - Chief` auth group.
- `chief` on the API is the first seated chief (US, EU, AU order);
  `chiefs` lists all three seats, filled or open.
- Migration `0052` seated each group's old single chief in their
  `PilotTimezone` home (else first bracket, else US).

## Who shows as chief

1. **Group:** its seated chiefs. With no seat filled, the tribe chief, as
   **Interim chief**. Else the alliance executor, as **Interim chief**.
2. **Tribe:** the tribe chief. Else the alliance executor, as
   **Interim chief**.

The executor is the owner of the character in
`settings.ALLIANCE_EXECUTOR_CHARACTER_ID` (env
`ALLIANCE_EXECUTOR_CHARACTER_ID`, default 634915984, BearThatCares); `0`
turns the fallback off. `tribes.helpers.chiefs.ChiefResolver` resolves all of
it and looks the executor up once per request.

**An interim chief acts as chief.** A chiefless group's tribe chief already
managed it; the executor now also leads a chiefless tribe and every group in
it:

- **Manages membership:** `user_can_manage_group` and `user_is_tribe_chief`
  (`tribes.helpers.permissions`) and the tribe-chief feature gates
  (`groups.helpers.feature_access._evaluate_tribe_chief`) count the
  executor for tribes without a chief (`tribes.helpers.executor`).
- **Gets the pings:** new applications (`tribes.membership_requested`), the
  pending-application reminder mention, help-ticket mentions for the group's
  category and external-guild alerts go to the acting chief.
- **Tribe - Chief auth group:** the executor is in it while any active tribe
  has no chief.
- The website treats the acting chief as the group's leader
  (`tribe_group_is_leader`).

The executor is not added as a member of the tribe's groups (tribe chiefs
are, by `ensure_tribe_chiefs_have_group_memberships`).

## Volunteering

- Any logged-in pilot can volunteer for an open seat, once, with an optional
  note (500 characters). A filled seat refuses offers.
- A group offer is for one timezone seat (`region`). Without one, the pilot's
  own timezone is used when that seat is open, else the first open seat. A
  group with some seats filled shows a quieter "open chief seats" banner
  instead of Help wanted, to pilots who don't already manage it.
- The offer DMs the executor (`tribes.chief_volunteered`), with **Appoint as
  chief** and **Not now** bot buttons (`tribe_chief:appoint:<id>`,
  `tribe_chief:decline:<id>`) and an **All volunteers** link to the seat's
  page.
- **Appoint** makes the pilot chief. For a group it also makes them an active
  member; for a tribe, `ensure_tribe_chiefs_have_group_memberships` adds them
  to every group. The seat's other open offers become `closed`; offers for
  the group's other timezone seats stay open.
- **Not now** leaves the seat open.
- The DM is edited once answered (`update_chief_volunteer_dm`): what happened,
  no buttons.

## Data model

`tribes.TribeGroupChief`: `tribe_group`, `region` (`US`, `EU`, `AU`),
`user`.

`tribes.TribeChiefVolunteer`: `tribe`, `tribe_group` (empty for the tribe
seat), `region` (a group seat's timezone), `user`, `note`, `status` (`pending`, `appointed`, `declined`,
`closed`), `decided_by`, `decided_at`.

## API

Additive fields on `TribeSchema` and `TribeGroupSchema`. `chief` keeps its
meaning: the real chief, or null.

| Field | Meaning |
|---|---|
| `chiefs` (groups) | The three timezone seats: `region`, `label` (USTZ...), `chief` (null if open or hidden), `is_open`, `has_volunteered` |
| `acting_chief` | Who the page shows as chief. Null if nobody, or if a hidden roster hides the group's own chief (a stand-in is always named) |
| `chief_is_interim` | The seat is open: show Help wanted |
| `can_appoint_chief` | The viewer is the executor |
| `has_volunteered` | The viewer has a pending offer for this seat |

| Route | Who |
|---|---|
| `POST /api/tribes/{tribe_id}/chief-volunteers` `{tribe_group_id?, region?, note}` | Any pilot |
| `GET /api/tribes/{tribe_id}/chief-volunteers?tribe_group_id=&region=` | Executor |
| `PUT /api/tribes/{tribe_id}/groups/{group_id}/chief` `{user_id, region}` | Superusers: fill, move or empty one seat |
| `POST /api/tribes/chief-volunteers/{id}/appoint` and `/decline` | Executor |
| `POST /api/tribes/chief-volunteers/{id}/discord-appoint` and `/discord-decline` `{discord_user_id}` | The bot, for the executor's click |

## Website

- Group and tribe headers show the acting chief's portrait; an interim one
  has an orange frame and an **Interim chief** label.
- A Help wanted banner sits above the group tabs and under the tribe header:
  who stands in, and **Volunteer** (a dialog with the note). Volunteering
  turns the button into **You volunteered**. The executor sees
  **Volunteers** instead, and the list (`#chief-volunteers`) under the
  banner, with Appoint (confirm) and Not now.
- Group catalog tiles add a **Help wanted** tag and show the interim chief.
- The Manage membership Leadership block shows the interim chief and the tag.
- Orange (`--attention`) means only this: the seat is open.
