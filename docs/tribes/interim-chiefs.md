# Interim chiefs and chief volunteers

A tribe or group with no chief still shows a chief: whoever stands in. The
page then says **Help wanted**, and pilots can volunteer. The alliance
executor gets a Discord DM and appoints someone, or says not now.
Wireframes: https://claude.ai/artifact/4KNNTmH9Q8LS3hMWwxKF7z

## Who shows as chief

1. **Group:** the group chief. Else the tribe chief, as **Interim chief**.
   Else the alliance executor, as **Interim chief**.
2. **Tribe:** the tribe chief. Else the alliance executor, as
   **Interim chief**.

The executor is the owner of the character in
`settings.ALLIANCE_EXECUTOR_CHARACTER_ID` (env
`ALLIANCE_EXECUTOR_CHARACTER_ID`, default 634915984, BearThatCares); `0`
turns the fallback off. `tribes.helpers.chiefs.ChiefResolver` resolves all of
it and looks the executor up once per request.

**Interim is display only.** It grants no chief permissions: approving
applications still follows `user_can_manage_group` (group chief, tribe chief,
admins).

## Volunteering

- Any logged-in pilot can volunteer for an open seat, once, with an optional
  note (500 characters). A filled seat refuses offers.
- The offer DMs the executor (`tribes.chief_volunteered`), with **Appoint as
  chief** and **Not now** bot buttons (`tribe_chief:appoint:<id>`,
  `tribe_chief:decline:<id>`) and an **All volunteers** link to the seat's
  page.
- **Appoint** makes the pilot chief. For a group it also makes them an active
  member; for a tribe, `ensure_tribe_chiefs_have_group_memberships` adds them
  to every group. The seat's other open offers become `closed`.
- **Not now** leaves the seat open.
- The DM is edited once answered (`update_chief_volunteer_dm`): what happened,
  no buttons.

## Data model

`tribes.TribeChiefVolunteer`: `tribe`, `tribe_group` (empty for the tribe
seat), `user`, `note`, `status` (`pending`, `appointed`, `declined`,
`closed`), `decided_by`, `decided_at`.

## API

Additive fields on `TribeSchema` and `TribeGroupSchema`. `chief` keeps its
meaning: the real chief, or null.

| Field | Meaning |
|---|---|
| `acting_chief` | Who the page shows as chief. Null if nobody, or if a hidden roster hides the group's own chief (a stand-in is always named) |
| `chief_is_interim` | The seat is open: show Help wanted |
| `can_appoint_chief` | The viewer is the executor |
| `has_volunteered` | The viewer has a pending offer for this seat |

| Route | Who |
|---|---|
| `POST /api/tribes/{tribe_id}/chief-volunteers` `{tribe_group_id?, note}` | Any pilot |
| `GET /api/tribes/{tribe_id}/chief-volunteers?tribe_group_id=` | Executor |
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
