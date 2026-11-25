# Tasks

`/tasks/` shows each pilot what is waiting on them (My tasks) and holds their task settings and the old Manage screens in its Settings tab. Team views and projects were taken off the website in November 2026 until alliance-wide task management is designed; their backend (`taskboard/teams.py`, the `/api/tasks/teams` and `/api/tasks/projects` endpoints, the project models and templates) is kept. Backend: the `taskboard` app, mounted at `/api/tasks`. Frontend: `src/pages/tasks/`, `src/components/blocks/tasks/` and the `tasks_*` partials.

The design aims to be useful without being overbearing. The rules below come from research into task tools (Linear, Asana, Basecamp, Things, Todoist, GitHub), into volunteer communities, and into EVE community tools (Alliance Auth, SeAT).

## Two kinds of task

- **Automatic** tasks are opened and closed by the site (`taskboard/rules.py`). Each rule collects the things that should have an open task right now. `taskboard.sync.sync_rule` opens a task for each new thing, refreshes the ones still there, and closes the ones that are gone. A task closes by itself once the pilot fixes what it is about. A pilot's own rules also refresh when they open their list, so a fixed token clears at once.
- **Assigned** tasks are written by a leader. Leaders are anyone who leads a corporation, a tribe or group, or reaches a manage screen (`taskboard.teams.can_assign`).

| Rule | Who | Weight |
|---|---|---|
| `reauth_character` | the pilot | needs you: one task for a broken main, one for all broken alts ([ESI health](../esi_health.md)) |
| `update_scopes` | the pilot | suggestion: a working token lacks a scope its groups have today, or a required group ([ESI health](../esi_health.md#scope-changes)) |
| `pick_main` | the pilot | needs you |
| `fleet_invite` | the pilot | needs you |
| `tribe_invitation` | the pilot | needs you |
| `set_timezone` | the pilot | suggestion (stops asking after 30 days) |
| `review_join_requests` | the group's chiefs | needs you, up for grabs |
| `review_applications` | the corporation's CEO and recruiters | needs you, up for grabs |
| `corp_director_token` | the corporation's CEO and directors | needs you, up for grabs: no director token, or the best one lacks a required scope |
| `corp_unlinked` | the corporation's CEO and directors | suggestion, up for grabs: characters in the corporation with no account here |
| `review_doctrine_changes`, `approve_reddit_posts`, `map_payout_codes`, `fix_calendar_feeds` | whoever reaches that manage screen | needs you, up for grabs |

To add a rule, write a `collect_*` function that returns `Item`s and add a `Rule` to `RULES`. The beat entry `[Tasks] Open and close automatic tasks` runs every rule every 15 minutes.

## Rules that keep it light

- **Needs you or suggestion.** Only needs-you tasks count: in the Neocom badge, the masthead, and leaders' views. Suggestions sit under "When you have a minute", have "Not now", and stop asking after 30 days (`sweep`). A pilot can bring one back from "Stopped asking".
- **The pilot is in control.** Snooze a week, hand an assigned or taken task back, hide suggestions, and pause everything (Account › Notifications). The On Leave and Alumni community statuses also pause tasks. Paused, On Leave and alumni pilots are left out of every leader count.
- **Shared work is up for grabs.** A team task belongs to nobody until someone takes it, so it never lands on everyone. A taken task with no activity for 14 days goes back to the team (`claim_expires_days`, set per rule).
- **Dates only when they are real.** New tasks default to "This week" or "No rush"; a date is opt-in. A task that waits on another shows "Waiting on …" instead of a date.
- **Repeating tasks never stack.** A weekly task opens its next copy only when the current one closes (`services._open_next_copy`), so a missed week stays one task.
- **Stale work closes itself.** An assigned task untouched for 30 days asks its author "Still needed?". With no answer, it stops two weeks later.
- **Nothing is taken away.** Ignoring a task removes no role or access.
- **Thanks.** Anyone but the assignee can thank a finished task once, and the pilot sees it on their closed list.

## Projects (not on the website)

A project has a lead, stages, tasks, and weekly updates (on track / at risk / off track). Templates (`ProjectTemplate` and `TemplateTask`, seeded in `0002_seed_project_templates`, edited in the Django admin) fill in the stages and tasks. A template task goes to the lead or to a manage screen's team (`goes_to = "screen:<key>"`), and its date is an offset from the start. A project started late doesn't open with overdue tasks, because past dates move to today. The Projects list marks an open project with no update in a week.

## Settings

The Tasks Settings tab is the old Manage hub (`/manage/` redirects there), plus the **Automatic tasks** and **Weekly DM** screens behind the `tasks.manage` gate:

- **Automatic tasks** (`/tasks/settings/rules/`): turn a rule on or off and set its timers. Turning a rule off cancels its open tasks.
- **Weekly DM** (`/tasks/settings/weekly/`): the day and hour the weekly list goes out.

## Discord messages

Every task DM is **opt-in**. Discord and Eve mail start off for all three, and a pilot turns each on in **Tasks › Settings** (every pilot has the tab; managers also see the Manage screens below their own settings). The same switches show on Account › Notifications. `taskboard/messages.py` sends them through the notifications app (`notifications/types/tasks.py`):

- **Weekly list.** An hourly job sends it on the set day and hour (Settings › Weekly DM, Sunday 17:00 EVE by default). It goes only to pilots who turned it on and have needs-you tasks that have waited 3 days or are due within a week. It never includes suggestions or snoozed tasks, and never goes to paused or On Leave pilots. One per week (idempotency key); deliveries are paced.
- **A leader reminds me.** (Not on the website while team views are off.) "Remind once" on a team's pilot list, shown only for pilots who turned reminders on (others show "Reminders off"). Only for a needs-you task that has waited `remind_after_days` (default 14, set per rule), once per task, and only by the pilot's own leaders.
- **Someone gives me a task.** Sent when a leader assigns one, if the pilot turned it on.

One exception to opt-in: a superuser can message pilots who need to re-add characters from Manage › ESI health (`tasks.esi_message`, Discord on by default). The site never sends it by itself, and a pilot gets it at most once a week. See [ESI health](../esi_health.md).

Messages that fall in a pilot's quiet hours (Tasks › Settings, EVE hours) wait in `TaskMessageHold` and go out when the quiet hours end. A pilot with closed DMs shows as "not delivered" on Settings › Weekly DM and still has the Neocom count.

## Not in this version

Assigned tasks that close when a linked thing changes (for example, when a doctrine is published).
