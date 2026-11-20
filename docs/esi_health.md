# ESI health

Which characters we can't read from EVE, who can fix it, and how hard we ask. Backend: the `esi_health` app (`/api/esi-health`), the `reauth_character`, `update_scopes`, `corp_director_token` and `corp_unlinked` task rules (`taskboard/rules.py`). Frontend: Manage › ESI health (`/manage/esi-health/`, the `esi_health_component` partial), the re-add block on Account › Characters (`EsiReaddBlock`), the Members tab's Re-add chip and director token warning, and the broken-main banner on the fleet schedule.

## Needs re-adding

One definition, in `esi_health.services.needs_readd_q`, used everywhere:

- the character belongs to an account and isn't exempt, and
- its token stopped refreshing (`esi_suspended`), or its token is gone while a token level is on record (it had one). Tokens deleted outside the refresh path never set `esi_suspended`; in November 2026 that left 15 alliance characters with no task and an "ACTIVE" label on the account page.

The pilot gets two tasks at most: "Re-add <main>" and "Re-add N alts". Re-add links go straight to EVE's login for that character; the add endpoint asks for the access the character had, so there is nothing to pick. "Re-add all" walks the alts one login at a time (`/account/?readd=alts`).

## Scope changes

A scope added to a group only reaches tokens granted afterwards. `ScopeRollout` records each change and how hard we ask (Manage › ESI health › Scope changes):

| Group | Choices | Effect |
|---|---|---|
| Character groups (Basic, ...) | Don't ask, Suggest | Suggest opens the `update_scopes` suggestion task and an Update link on Account › Characters |
| Director | Don't ask, Require | Require counts the scope in the director token check: corporations whose best token lacks it get `corp_director_token` and the Members tab warning |

Seeded (`0002_seed_scope_rollouts`): structure search in Basic, not asked (only structure search uses it, and 664 of 824 tokens predate it); corporation projects in Director, required.

## Discord messages

Pilots get no Discord message about ESI unless they turned task messages on. The exception is the message a superuser sends from Manage › ESI health, to everyone who needs to re-add or to one pilot (`tasks.esi_message`, Discord on by default so it reaches pilots who never opted in; a pilot can turn it off in Account › Notifications). It skips pilots On Leave, sends at most once a week per pilot (`EsiMessage`, `MESSAGE_COOLDOWN`), names the pilot's own characters, and is paced like every other DM.

## Access

Manage › ESI health is behind `esi_health.manage`, an unwired `auth_group` feature: only superusers pass. A corporation's director token status is for the people who see its Members tab.
