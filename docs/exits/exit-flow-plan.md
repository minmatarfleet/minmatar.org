# Corporation exit flow: design summary and build plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** historical: the build plan, carried out in one pull request (the four parts together). The current
description is [exit-flow-design.md](exit-flow-design.md); deviations from this plan are listed in that pull request.

**Goal:** Spot pilots who leave tracked corporations, have the CEO record why, warn other corporations about pilots
who shouldn't rejoin, and send voluntary leavers one survey that only the Alliance Executor reads.

**Architecture:** A new `exits` Django app owns member snapshots, departures, CEO answers, flags, flagged joins and
recruiter alerts. The hourly corporation member sync hands each tracked corporation's member list to it. Exit and
alliance move surveys live in the existing `surveys` app, with their own invite and response tables. CEO and join
tasks are task-board rules (`backend/taskboard/rules.py`). The website adds a Departures tab, a history panel on
the application page and a no-login survey page, all as htmx partials built from Rust components.

**Tech stack:** Django + Django Ninja, Celery (`AppTask`, routes in `backend/app/queues.py`), django-esi through
`eveonline.client.EsiClient`, Astro + htmx + Alpine, Rust components, Vitest.

**Spec:** [exit-flow-design.md](exit-flow-design.md) and the issue's requirements. Section numbers below
("design 06") point at that document's numbered sections.

## Design summary

The decisions made on top of the issue, which this plan builds:

| Topic | Decision |
| --- | --- |
| Flagged pilot joins in game | Recruiters often invite in game and `applications/joined.py` then accepts the application by itself, so the accept confirmation never shows. The member sync also spots joins: a flagged pilot appearing in a tracked corporation opens a task for that CEO (keep with a note, or remove). |
| Survey can't be delivered | If ESI refuses the Eve mail (a CSPA charge), send the same text as a Discord DM when the pilot's account has Discord linked; otherwise mark the invite "not delivered". |
| Where the CEO answers | A CEO-only **Departures** tab on the corporation page. The task links to it, and answers stay findable and editable after the task closes. |
| History across corporations | Recruiters see every past departure from alliance corporations (reason, CEO, note), not only can't-rejoin flags. |
| Where alerts go | Never the application's Discord thread: its starter post mentions the applicant (`application_starter_message`), so they are in it. A new recruiter-only alerts channel gets a short alert that pings the corporation's recruiter role and links the application. The details are on the application page, behind `can_review_applications`. |
| Alert volume | At most one alert per application and reason. Alerts only for a can't-rejoin flag or "kicked for another reason". A later answer re-alerts only when it adds a can't-rejoin flag. No history, no alert. |
| Code layout | Exit surveys in `surveys` (the issue asks for it): its definitions, typed answers and `SurveyField` fit, but `SurveyResponse` requires a user and campaigns are one per quarter, so the exit surveys get their own invite and response tables. Everything else in a new `exits` app. |

Proposals still to confirm in review are tagged **[proposal]** in the design. The ones that change the build are listed under
"Open questions" at the end.

## Global constraints

- Grace period: **48 hours** from first seen missing. Survey link: valid **30 days**, one response. Undo window
  before a survey is sent: **1 hour**.
- Reasons, stored values: `kicked_inactive`, `kicked_other`, `left`. Kinds: `exit`, `alliance_move`.
- NPC corporations: corporation IDs from **1000000 to 1999999**.
- One survey per person, ever: per account when known, otherwise per character. Exit and alliance move share it.
- Survey answers: no API outside the token endpoints, admin pages only for `tribes.helpers.executor.executor_user_id()`.
- Pilots never see a departure, an answer, a flag, their history or an alert.
- Backend rules: one method and path per endpoint module (`.claude/rules/one-file-per-endpoint.md`); tasks are
  `AppTask`, routed by prefix in `backend/app/queues.py` (`exits.` goes to `community`); no network in tests
  (`app/test_network_guard.py`); after an endpoint change regenerate `openapi.json` and `api.d.ts`
  (`.claude/rules/api-types.md`).
- Website rules: htmx for server state, Alpine only for local UI; Rust components first
  (`frontend/app/rust/CATALOG.md`); i18n through `t()`; types are aliases of the generated schema.
- Copy: the CEO notice and the survey texts are fixed in the design (sections 04 and 07); use them as
  written.

## Review focus

The cases the tasks' own tests don't naturally reach, most likely to bite first. Each has a test in the task named.

1. **A failed or empty ESI member read** must not create departures for every member (Task 1.2,
   `test_empty_member_list_is_skipped`).
2. **A tracked corporation outside `member_corporations()`** (Minmatar Extraction Company): its CEO must still
   get the departures task, which `led_corporations` alone would hide (Task 2.1, `test_ceo_role_outside_member_corporations`).
3. **The applicant opening their own application page** must not see the history panel (Task 3.2,
   `test_applicant_gets_403_for_history`).
4. **A CEO clicking "left on their own" by mistake** must be able to undo it within the hour, with no mail sent
   (Task 4.3, `test_changed_answer_within_hour_sends_nothing`).
5. **ESI's refusal for a CSPA charge**: its exact response must be checked against a real send on the dev server
   before 4.3 merges; the test pins what the helper does with it (Task 4.2, `test_cspa_refusal_is_not_retried`).

---

# Part 1: Departures (backend pull request)

Ships: the Track exits checkbox, snapshots, departures with the grace period and destination, and the director
token task for tracked corporations. Nothing pilot-facing.

### Task 1.1: The `exits` app, its models and the Track exits checkbox

```text
Create: backend/exits/__init__.py, apps.py, admin.py, models.py, migrations/0001_initial.py
Create: backend/exits/tests/__init__.py, backend/exits/tests/test_models.py
Modify: backend/eveonline/models/corporations.py (track_exits), its migration, backend/eveonline/admin.py
Modify: backend/app/settings_common.py (INSTALLED_APPS), backend/app/queues.py (ROUTES)
```

**Interfaces:**
- Produces: `EveCorporation.track_exits: BooleanField(default=False)`.
- Produces `exits.models`:
  - `MemberSnapshot`: `corporation` (OneToOne `EveCorporation`), `member_ids` (JSON list of ints),
    `alliance_id` (BigInteger, null), `taken_at`.
  - `Departure`: `corporation` (FK), `character_id` (BigInteger, indexed), `user` (FK User, null),
    `first_missing_at`, `status` (`pending` · `dropped` · `confirmed`, default `pending`), `confirmed_at` (null),
    `destination_corporation_id` (null), `kind` (`""` · `exit` · `alliance_move`), `destination_is_npc` (bool),
    `reason` (`""` · `kicked_inactive` · `kicked_other` · `left`), `can_rejoin` (bool, null), `note` (text),
    `answered_by` (FK User, null), `answered_at` (null), `survey_due_at` (null). Index `(corporation, status)`.
- The admin shows `track_exits` on the corporation change form, and lists both models read-only.

- [ ] **Step 1: Write the failing test** `test_departure_defaults`: a `Departure` created with a corporation,
  character ID and `first_missing_at` has `status == "pending"`, `reason == ""`, `can_rejoin is None`; and
  `test_track_exits_defaults_off`: a new `EveCorporation` has `track_exits is False`.
- [ ] **Step 2: Run it and see it fail.** From `backend/`:
  `PIPENV_DONT_LOAD_ENV=1 pipenv run python manage.py test exits --settings=app.settings_test` fails on the import.
- [ ] **Step 3: Add the app, the models, the field and both migrations** (`makemigrations exits eveonline`).
  Add `"exits."` to `ROUTES` as `"community"`.
- [ ] **Step 4: Run it and see it pass.** Also run `app.tests.test_queue_standards`.
- [ ] **Step 5: Commit** `Add the exits app and the Track exits checkbox (#3198)`.

### Task 1.2: Compare member lists

```text
Create: backend/exits/helpers/__init__.py, backend/exits/helpers/snapshots.py
Create: backend/exits/tests/test_snapshots.py
```

**Interfaces:**
- Consumes: `MemberSnapshot`, `Departure`, `EveCorporation.track_exits`.
- Produces `exits.helpers.snapshots`:
  - `@dataclass SnapshotResult: left: set[int]; joined: set[int]; skipped: str` (`""` when compared,
    otherwise `"first_sync"`, `"empty"` or `"alliance_changed"`).
  - `record_members(corporation: EveCorporation, member_ids: list[int], now: datetime) -> SnapshotResult`:
    stores the list and returns who left and joined. For `left`, creates a pending `Departure` (with `user` from
    the character's account when known) unless one is already pending for that character and corporation. For
    every member in the list, drops pending departures of that corporation (they came back).
  - `stop_tracking(corporation: EveCorporation) -> None`: deletes the snapshot and marks pending departures
    `dropped`.

- [ ] **Step 1: Write the failing tests:**
  - `test_first_sync_only_stores`: no snapshot, list `[1, 2]` → `skipped == "first_sync"`, no departures.
  - `test_missing_member_opens_departure`: snapshot `[1, 2, 3]`, list `[1, 2]` → `left == {3}`, one pending
    departure for 3.
  - `test_back_within_grace_is_dropped`: pending departure for 3, then list `[1, 2, 3]` → that departure's status
    is `dropped`.
  - `test_empty_member_list_is_skipped`: snapshot `[1, 2]`, list `[]` → `skipped == "empty"`, no departures, the
    stored list is still `[1, 2]`.
  - `test_alliance_changed_resets`: snapshot with `alliance_id` A and one pending departure, corporation now in
    alliance B → `skipped == "alliance_changed"`, the pending departure is `dropped`, the snapshot holds the new
    list.
  - `test_joined_members_are_returned`: snapshot `[1]`, list `[1, 4]` → `joined == {4}`.
  - `test_stop_tracking_drops_pending`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement `record_members` and `stop_tracking`.** Wrap each call in one transaction.
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit** `Compare tracked corporations' member lists (#3198)`.

### Task 1.3: Feed the member sync into it

```text
Modify: backend/eveonline/helpers/corporations/update.py (update_corporation_members_and_roles)
Modify: backend/eveonline/tasks/corporations.py (update_corporation)
Modify: backend/eveonline/admin.py (call stop_tracking when track_exits is unticked)
Test:   backend/exits/tests/test_sync_hook.py
```

**Interfaces:**
- Consumes: `record_members`, `stop_tracking`.
- The members sync runs for a corporation that is active and alliance or associate (as today) **or** has
  `track_exits`. After a successful members call, when `corporation.track_exits`, it calls
  `record_members(corporation, member_ids, timezone.now())`. A failed members call calls nothing.

- [ ] **Step 1: Write the failing tests** with `EsiClient` mocked:
  `test_tracked_militia_corporation_is_synced` (a tracked corporation of type `militia` reaches
  `record_members`), `test_untracked_corporation_is_not_recorded`, `test_failed_members_call_records_nothing`,
  `test_unticking_track_exits_stops_tracking` (saving the admin form with the box cleared drops pending
  departures).
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Change the two conditions and add the call.** Unticking is caught in the corporation admin's
  `save_model` (compare with the stored value).
- [ ] **Step 4: Run them and the eveonline corporation tests** (`eveonline.tests`) and see them pass.
- [ ] **Step 5: Commit** `Hand tracked corporations' member lists to exits (#3198)`.

### Task 1.4: Confirm departures after 48 hours, and where they went

```text
Create: backend/exits/helpers/departures.py, backend/exits/tasks.py
Modify: backend/app/settings_celery.py (beat entry)
Test:   backend/exits/tests/test_departures.py
```

**Interfaces:**
- Produces `exits.helpers.departures`:
  - `GRACE = timedelta(hours=48)`.
  - `is_npc_corporation(corporation_id: int | None) -> bool`: `1000000 <= id <= 1999999`.
  - `classify(destination_corporation_id: int | None) -> str`: `alliance_move` when the ID is an
    `alliance_corporations()` corporation or a `track_exits` corporation, else `exit`.
  - `confirm_due(now: datetime) -> int`: every pending departure older than `GRACE` whose character is still not
    in that corporation (`EveCharacter.corporation_id`, kept fresh by the 15-minute affiliation sync) becomes
    `confirmed`, with `confirmed_at`, `destination_corporation_id`, `kind` and `destination_is_npc`. A character
    back in the corporation is `dropped`. No `EveCharacter` row or no corporation: `kind = exit`,
    `destination_corporation_id = None`. Returns the number confirmed.
- Produces the task `exits.tasks.confirm_departures()` (`@app.task(exclusive=15 * 60)`) calling `confirm_due`, and
  a beat entry every 15 minutes with `"options": {"expire_seconds": 15 * 60}`.

- [ ] **Step 1: Write the failing tests:** `test_not_confirmed_before_48_hours`, `test_npc_destination_is_exit`
  (destination 1000167 → `exit`, `destination_is_npc`), `test_alliance_corporation_is_alliance_move`,
  `test_tracked_non_alliance_corporation_is_alliance_move`, `test_back_in_corporation_is_dropped`,
  `test_unknown_character_is_exit_without_destination`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement the helpers and the task; add the beat entry.**
- [ ] **Step 4: Run them, plus `app.tests.test_queue_standards`.**
- [ ] **Step 5: Commit** `Confirm departures after 48 hours and record where they went (#3198)`.

### Task 1.5: Director token task for tracked corporations

```text
Modify: backend/taskboard/rules.py (collect_corp_director_token)
Test:   backend/taskboard/tests/test_tasks.py
```

- [ ] **Step 1: Write the failing test** `test_director_token_task_for_tracked_corporation`: a `track_exits`
  corporation outside the alliance with no director token gets an item titled "Add a director token" whose
  detail is "Departures can't be tracked without it".
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Collect `alliance_corporations()` plus `track_exits` corporations** (distinct), and use that detail
  line for tracked corporations with no token.
- [ ] **Step 4: Run the taskboard tests and see them pass.**
- [ ] **Step 5: Commit** `Ask tracked corporations for a director token (#3198)`, then run the backend review and
  open Part 1's pull request (`Refs #3198`).

---

# Part 2: CEO answers and the Departures tab

Ships: the task, the CEO's answers (with flags), and the tab. Depends on Part 1.

### Task 2.1: A CEO-only task

```text
Modify: backend/eveonline/helpers/corporations/permissions.py (is_corporation_ceo)
Modify: backend/taskboard/teams.py (Membership._corporation), backend/taskboard/rules.py
Test:   backend/exits/tests/test_tasks.py
```

**Interfaces:**
- Produces `is_corporation_ceo(user: User, corporation: EveCorporation) -> bool` (any of the user's characters is
  the CEO; `owned_by_q`).
- `Membership._corporation` treats `team_role == "ceo"` as `is_corporation_ceo`; superusers keep the existing
  branch. The user's task list includes CEO-role tasks for every corporation they are CEO of, including tracked
  corporations outside `member_corporations()`.
- Produces the rule `exit_departures` (`AUDIENCE_CEO`, `Weight.NEEDS_YOU`, `watch=(Departure,)`): one `Item` per
  tracked corporation with confirmed, unanswered departures. `source_key = "corporation:<id>"`,
  `title = "Tell us why {n} pilot left"` / `"... pilots left"`, `link_url = "/alliance/corporations/<id>/#departures"`,
  `link_label = "Answer"`, `team_role = "ceo"`, `since` = the oldest `confirmed_at`.

- [ ] **Step 1: Write the failing tests:** `test_one_task_per_corporation` (two departures → one item, "2 pilots"),
  `test_task_closes_when_all_answered` (after answering both, the next sync closes it), `test_director_cannot_act`,
  `test_ceo_role_outside_member_corporations`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement the helper, the role and the rule.**
- [ ] **Step 4: Run them and the taskboard tests.**
- [ ] **Step 5: Commit** `Ask the CEO why pilots left (#3198)`.

### Task 2.2: Answers and flags

```text
Create: backend/exits/models.py (RejoinFlag), migration 0002
Create: backend/exits/helpers/answers.py, backend/exits/helpers/grouping.py
Test:   backend/exits/tests/test_answers.py
```

**Interfaces:**
- Produces `RejoinFlag`: `character_id`, `user` (FK, null), `departure` (FK), `corporation` (FK), `note`, `set_by`,
  `set_at`, `cleared_by` (null), `cleared_at` (null). "Active" means `cleared_at is null`.
- Produces `exits.helpers.answers`:
  - `class AnswerError(Exception)` with `status_code`.
  - `answer(by: User, corporation: EveCorporation, departure_ids: list[int], *, reason: str, can_rejoin: bool | None, note: str) -> list[Departure]`.
    Rules: only the corporation's CEO (or a superuser); only confirmed departures of that corporation;
    `can_rejoin` is required for kicks and ignored for `left`; `can_rejoin is False` needs a non-empty note;
    the reason is locked once an `ExitSurveyInvite` exists for the departure (Part 4: until then, nothing locks).
    `left` on an alliance move or exit sets `survey_due_at = now + 1 hour`; any other reason clears it.
    `can_rejoin is False` creates an active `RejoinFlag` (one per departure); changing it to true clears it.
  - `clear_flag(by: User, flag: RejoinFlag) -> RejoinFlag`: the current CEO of `flag.corporation` or a superuser.
- Produces `exits.helpers.grouping.group(departures: list[Departure]) -> list[list[Departure]]`: the same `user`,
  `first_missing_at` within `GRACE` of the group's first, ordered newest first; unregistered characters are
  groups of one.
- The `RejoinFlag` admin lists flags (character, corporation, set by, note, active) and has a "Clear" action that
  calls `clear_flag` with the admin user, as the issue asks.

- [ ] **Step 1: Write the failing tests:** `test_bulk_answer_sets_every_row`, `test_kick_needs_can_rejoin`,
  `test_cant_rejoin_needs_note`, `test_cant_rejoin_creates_flag`, `test_rejoin_true_clears_flag`,
  `test_left_sets_survey_due_in_an_hour`, `test_director_is_refused`, `test_other_corporations_rows_refused`,
  `test_alts_group_together`, `test_clear_flag_by_new_ceo`, `test_admin_clear_action_records_who`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** Each `answer` call is one transaction.
- [ ] **Step 4: Run them and see them pass.**
- [ ] **Step 5: Commit** `Record CEO answers and can't-rejoin flags (#3198)`.

### Task 2.3: The departures API

```text
Create: backend/exits/endpoints/__init__.py, schemas.py, get_departures.py, post_departure_answers.py,
        post_flag_clear.py, backend/exits/router.py
Modify: backend/app/urls.py (api.add_router("exits", ...)),
        backend/eveonline/endpoints/corporations/get_corp_member_details.py and schemas.py (can_view_departures)
Regenerate: frontend/app/src/types/generated/openapi.json, api.d.ts
Test:   backend/exits/tests/test_endpoints.py
```

**Interfaces:**
- `GET /api/exits/corporations/{corporation_id}/departures?state=open|answered|all` → 200
  `list[DepartureGroupResponse]` (403 unless CEO or superuser). `DepartureGroupResponse`: `departure_ids`,
  `character_id`, `character_name`, `alt_names: list[str]`, `registered: bool`, `months_in_corporation: int | None`
  (from `EveCharacterCorporationHistory`), `first_missing_at`, `destination_corporation_id`,
  `destination_name`, `kind`, `destination_is_npc`, `reason`, `can_rejoin`, `note`, `flag_id`, `survey_sent_at`.
- `POST /api/exits/corporations/{corporation_id}/departures/answers` body `DepartureAnswerRequest`
  (`departure_ids`, `reason`, `can_rejoin`, `note`) → 200 the updated groups; `AnswerError` → its status.
- `POST /api/exits/flags/{flag_id}/clear` → 200 `{}`.
- `CorporationMemberAccess.can_view_departures: bool = False` (true for the CEO of a tracked corporation).

- [ ] **Step 1: Write the failing tests:** `test_ceo_lists_open_departures`, `test_director_gets_403`,
  `test_answers_endpoint_returns_groups`, `test_can_view_departures_only_for_ceo`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement the endpoints, then regenerate the schema**
  (`UPDATE_CONTRACTS=1 ... test app.tests.test_openapi_schema`, then `npm run gen:api` in `frontend/app`).
- [ ] **Step 4: Run them and `app.tests.test_openapi_schema`.**
- [ ] **Step 5: Commit** `Departures API for the CEO (#3198)`.

### Task 2.4: The Departures tab

```text
Create: frontend/app/src/components/blocks/CorporationDepartures.astro (feature block)
Create: frontend/app/src/pages/partials/corporation_departures_component.astro
Create: frontend/app/rust/stories/features/corporations/CorporationDepartures.stories.ts + fixtures
Create: frontend/app/src/helpers/api.minmatar.org/exits.ts
Modify: frontend/app/src/types/api.minmatar.org.ts (aliases), frontend/app/src/i18n/ui.ts
Modify: frontend/app/src/pages/alliance/corporations/[corporation]/index.astro ('departures' tab)
Test:   frontend/app/testing/helpers/corporation_departures.test.ts
```

**Interfaces:**
- Types: `DepartureGroup = ApiResponse<'DepartureGroupResponse'>`, `DepartureAnswer = ApiRequest<'DepartureAnswerRequest'>`.
- Helpers: `get_departures(token, corporation_id, state)`, `post_departure_answers(token, corporation_id, body)`,
  `clear_rejoin_flag(token, flag_id)`.
- The tab shows only when `member_access.can_view_departures`; the panel loads the partial with `LazyPartial`.
  The partial renders filter chips (Needs an answer, the default · Answered · All, with counts), the progress
  line, the bulk bar, the table inside `XFadeScroll`, and `EmptyState` / `ErrorRefetch`. Saving posts the form to
  the partial, which calls the answers endpoint and re-renders. Alpine holds only the ticked rows and the bulk
  choice. "Can't rejoin" opens the confirm dialog with the copy from design 06, and its note field is required.
- Copy: the "Who sees your answers" notice from design 04, verbatim.

- [ ] **Step 1: Write the failing tests:** a pure helper `departure_row_view(group)` returning tags
  (`npc`, `exit`, `alliance_move`) and whether "can rejoin" shows (kicks only), tested in
  `corporation_departures.test.ts`; stories `Open`, `AllAnswered`, `WithAlts` with `play()` checks.
- [ ] **Step 2: Run them and see them fail.**
  `cd frontend/app && npx vitest run testing/helpers/corporation_departures.test.ts`
- [ ] **Step 3: Build the block, partial, tab and stories** from `frontend/app/rust/CATALOG.md` components; regenerate
  the catalog (`UPDATE_CATALOG=1 npx vitest run testing/rust/catalog.test.ts`).
- [ ] **Step 4: Run `npm run test` and `npm run check`; look at the tab at desktop width and 390px.**
- [ ] **Step 5: Commit** `Departures tab for the CEO (#3198)`, run the frontend and backend reviews, and open
  Part 2's pull request with screenshots (`scripts/pr_screenshots.py`).

---

# Part 3: Flags and history in the application flow

Ships: alliance history for recruiters, the alerts channel, the accept confirmation, flagged joins and their task,
and the Members tab tag. Depends on Part 2.

### Task 3.1: Alliance history

```text
Create: backend/exits/helpers/history.py
Test:   backend/exits/tests/test_history.py
```

**Interfaces:**
- Produces `@dataclass HistoryEntry: departure_id, corporation_id, corporation_name, left_at, reason, can_rejoin,
  note, answered_by_name, flag_active: bool`.
- `character_ids_for(user: User | None, character_ids: Iterable[int]) -> set[int]`: the given IDs plus every
  character on the user's account.
- `history_for(user: User | None, character_ids: Iterable[int]) -> list[HistoryEntry]`: answered departures of
  those characters, newest first; one entry per alt group (`grouping.group`).
- `active_flags_for(user: User | None, character_ids: Iterable[int]) -> list[RejoinFlag]`.

- [ ] **Step 1: Failing tests:** `test_history_covers_the_account`, `test_unanswered_departures_left_out`,
  `test_alt_group_is_one_entry`, `test_cleared_flag_is_not_active`.
- [ ] **Steps 2–4: Run, implement, pass.**
- [ ] **Step 5: Commit** `Alliance history of a pilot (#3198)`.

### Task 3.2: History on the application page

```text
Create: backend/exits/endpoints/get_application_history.py
Modify: frontend/app/src/components/blocks/CorporationApplication.astro, its page, i18n, exits.ts helper
Regenerate: openapi.json, api.d.ts
Test:   backend/exits/tests/test_endpoints.py, a story for the history panel
```

**Interfaces:**
- `GET /api/exits/applications/{application_id}/history` → 200 `list[HistoryEntryResponse]`; 403 unless
  `can_review_applications(user, corporation)` for the application's corporation.
- The page fetches it only for reviewers and renders the panel above the actions (tags: Can't rejoin, Inactive
  kick, Other kick, Left). Nothing renders for anyone else or for an empty list.

- [ ] **Step 1: Failing tests:** `test_recruiter_sees_history`, `test_applicant_gets_403_for_history`,
  `test_other_corporation_recruiter_gets_403`.
- [ ] **Steps 2–4: Run, implement (backend, regenerate, frontend), pass; check the page as the applicant and as a
  recruiter.**
- [ ] **Step 5: Commit** `Show recruiters a pilot's alliance history (#3198)`.

### Task 3.3: Accept with confirmation

```text
Create: backend/exits/models.py (FlagAcceptance), migration
Modify: backend/applications/router.py (accept_corporation_application)
Modify: frontend/app/src/components/blocks/CorporationApplication.astro, applications.ts helper
Test:   backend/exits/tests/test_accept.py
```

**Interfaces:**
- `FlagAcceptance`: `application` (FK), `flag_ids` (JSON), `accepted_by`, `accepted_at`.
- The accept endpoint takes `confirm_flags: bool = False` (query). With active flags for the applicant and no
  confirmation → 409 `FlaggedApplicantResponse` (`detail`, `flags: list[HistoryEntryResponse]`); with it → accepts
  and stores a `FlagAcceptance`. No flags: unchanged.
- The existing accept dialog shows the flag text from design 06 ("Accept a pilot marked can't rejoin?") when the
  page knows of active flags, and its confirm sends `confirm_flags=true`.

- [ ] **Step 1: Failing tests:** `test_flagged_accept_needs_confirmation`, `test_confirmed_accept_is_recorded`,
  `test_unflagged_accept_unchanged`.
- [ ] **Steps 2–4: Run, implement, regenerate the schema, pass.**
- [ ] **Step 5: Commit** `Confirm before accepting a flagged pilot (#3198)`.

### Task 3.4: Recruiter alerts

```text
Create: backend/exits/models.py (RecruiterAlert), migration; backend/exits/helpers/alerts.py
Modify: backend/exits/tasks.py, backend/applications/signals.py, backend/applications/router.py (transfer),
        backend/exits/helpers/answers.py (alert open applications on a new flag),
        backend/app/settings_env.py (DISCORD_RECRUITER_ALERTS_CHANNEL_ID)
Test:   backend/exits/tests/test_alerts.py
```

**Interfaces:**
- `RecruiterAlert`: `application` (FK), `reason` (`flag` · `kicked_other`), `sent_at`, `message_id`; unique
  `(application, reason)`.
- `DISCORD_RECRUITER_ALERTS_CHANNEL_ID = env_int("DISCORD_RECRUITER_ALERTS_CHANNEL_ID", 0)`; 0 means alerts are
  logged and not sent.
- `alert_reason(application) -> str | None`: `flag` if any active flag, else `kicked_other` if any history entry has
  that reason, else None.
- `send_alert(application_id: int) -> bool`: posts once per `(application, reason)` in the channel:
  the corporation's recruiter role mention (`applications.discord._recruiter_role_mention`), the line
  "⚠ {name}, applying to {corporation}, has alliance history", "Includes a can't-rejoin flag from {corporation}."
  for flags, and the link `applications.discord.application_url(application)`. No reasons, notes or names of
  other CEOs in the message.
- Task `exits.tasks.alert_application(application_id)`, queued after commit when an application is created or
  transferred, and for every pending application of the pilot when `answer` creates a flag.

- [ ] **Step 1: Failing tests** (Discord client mocked): `test_no_history_no_alert`, `test_inactive_kick_no_alert`,
  `test_kicked_other_alerts_once`, `test_flag_alert_after_kicked_other_alert`, `test_new_flag_alerts_open_applications`,
  `test_transfer_alerts_new_corporation`, `test_alert_has_no_notes`.
- [ ] **Steps 2–4: Run, implement, pass.**
- [ ] **Step 5: Commit** `Alert recruiters about pilots with history (#3198)`.

### Task 3.5: Flagged joins, their task, and the Members tab tag

```text
Create: backend/exits/models.py (FlaggedJoin), migration; backend/exits/helpers/joins.py
Create: backend/exits/endpoints/post_flagged_join_keep.py, post_flagged_join_remove.py
Modify: backend/exits/helpers/snapshots.py (call record_flagged_joins), backend/taskboard/rules.py
Modify: backend/eveonline/endpoints/corporations/get_corp_member_details.py (has_alliance_history),
        the members table partial and i18n
Test:   backend/exits/tests/test_joins.py
```

**Interfaces:**
- `FlaggedJoin`: `corporation`, `character_id`, `user` (null), `flag_ids` (JSON), `seen_at`, `outcome`
  (`""` · `kept` · `removed`), `note`, `resolved_by` (null), `resolved_at` (null).
- `record_flagged_joins(corporation, joined_ids: set[int], now) -> int`: a `FlaggedJoin` for each joined character
  with active flags (account-wide); called from `record_members` after a compared sync.
- `resolve_removed(corporation, member_ids)`: open joins whose character is gone become `removed`.
- Rule `exit_flagged_join` (`AUDIENCE_CEO`, `team_role = "ceo"`, `watch=(FlaggedJoin,)`): one item per open join,
  title "{name} joined {corporation}. They're marked can't rejoin", detail the newest flag's corporation, CEO, date
  and note, link to the Members tab.
- `POST /api/exits/flagged-joins/{id}/keep` body `{note}` (required) → `kept`; `POST .../remove` → leaves it open
  and marked "removal expected" until the sync resolves it.
- `CorporationMemberDetails.has_alliance_history: bool` for CEO and directors; the members table shows a History
  tag that opens the history list in a dialog.

- [ ] **Step 1: Failing tests:** `test_flagged_join_opens_task`, `test_unflagged_join_opens_nothing`,
  `test_keep_needs_note`, `test_removed_resolves_on_next_sync`, `test_history_tag_only_for_leadership`.
- [ ] **Steps 2–4: Run, implement, regenerate the schema, pass; check the Members tab.**
- [ ] **Step 5: Commit** `Tell the CEO when a flagged pilot joins (#3198)`, run both reviews and open Part 3's
  pull request with screenshots. Ops: create the alerts channel, restrict it to recruiter roles, set the setting.

---

# Part 4: Surveys

Ships: the two survey definitions, sending with the Discord fallback, the no-login page and Executor-only
storage. Depends on Part 2.

### Task 4.1: Definitions and storage in `surveys`

```text
Create: backend/surveys/definitions/exit.py
Create: backend/surveys/models/exit_invite.py, exit_response.py; migration
Modify: backend/surveys/models/__init__.py, backend/surveys/admin.py
Test:   backend/surveys/tests/test_exit_surveys.py
```

**Interfaces:**
- `EXIT_SURVEY` (`key="exit"`) and `ALLIANCE_MOVE_SURVEY` (`key="alliance_move"`), both `SurveyDefinition`s with the
  issue's draft questions (four `scale5` ratings required; the rest optional), in `EXIT_DEFINITIONS:
  dict[str, SurveyDefinition]`, separate from `SURVEY_DEFINITIONS`. `EXIT_DEFINITION_VERSION = 1`.
- `ExitSurveyInvite`: `departure` (OneToOne), `character_id`, `user` (null), `definition_key`, `definition_version`,
  `channel` (`eve_mail` · `discord_dm` · `""`), `status` (`sent` · `not_delivered`), `sent_at`, `expires_at`,
  `responded_at` (null).
- `ExitSurveyResponse` (`invite` OneToOne, `corporation_id`, `definition_key`, `definition_version`, `submitted_at`)
  and `ExitSurveyAnswer` (the same value columns as `SurveyAnswer`, unique `(response, question_key)`).
- Admin for these three: view only, and only when `request.user.pk == executor_user_id()`.

- [ ] **Step 1: Failing tests:** `test_exit_definitions_not_in_campaigns`, `test_ratings_are_required`,
  `test_admin_hidden_from_other_superusers`.
- [ ] **Steps 2–4: Run, implement, pass. Also run `surveys` tests to show the community survey is unchanged.**
- [ ] **Step 5: Commit** `Exit and alliance move survey definitions (#3198)`.

### Task 4.2: Mail one character

```text
Modify: backend/notifications/channels.py
Test:   backend/notifications/tests (the existing channel tests' module)
```

**Interfaces:**
- `send_eve_mail_to_character(character_id: int, subject: str, body: str) -> None`, split out of `_send_eve_mail`
  (same rate bucket, sender and error mapping); `_send_eve_mail` calls it with the main's ID.
- `class EveMailRefused(ChannelSendError)` raised, not retryable, when ESI refuses the mail for a CSPA charge.

- [ ] **Step 1: Failing tests:** `test_mail_goes_to_given_character`, `test_cspa_refusal_is_not_retried`
  (the refusal response, as confirmed on the dev server, raises `EveMailRefused`), and the existing Eve mail tests
  still pass.
- [ ] **Steps 2–4: Run, implement, pass.**
- [ ] **Step 5: Commit** `Send an Eve mail to any character (#3198)`.

### Task 4.3: Send due surveys

```text
Create: backend/surveys/helpers/exit_tokens.py, backend/surveys/helpers/exit_sending.py
Modify: backend/surveys/tasks.py, backend/app/settings_celery.py, backend/exits/helpers/answers.py (lock)
Test:   backend/surveys/tests/test_exit_sending.py
```

**Interfaces:**
- `exit_tokens.mint(invite) -> str` and `exit_tokens.invite_for(token) -> ExitSurveyInvite` (raises `TokenInvalid`),
  `signing` with salt `"surveys.exit"`, `max_age = 30 days`; URL `site_url("/exit-survey/<token>/")`.
- `exit_sending.send_due(now) -> int`: departures with `survey_due_at <= now`, `reason == "left"` and no invite.
  One invite per alt group, addressed to the account's main when it is in the group, else the group's first
  departure. Skip, with no invite, when anyone on the account (or this character, unregistered) already has an
  invite, or `destination_corporation_id is None`. Mail first; on `EveMailRefused`, the Discord DM through
  `notifications.channels._send_discord` when the account has Discord; else `status = not_delivered`.
  Mail and DM texts are the design 07 copy, with the alliance move variant.
- Task `surveys.tasks.send_exit_surveys()` (`exclusive=15 * 60`), beat every 15 minutes.
- `answers.answer` now refuses a reason change once an invite exists.

- [ ] **Step 1: Failing tests:** `test_not_sent_within_the_hour`, `test_changed_answer_within_hour_sends_nothing`,
  `test_exit_gets_exit_survey`, `test_alliance_move_gets_move_survey`, `test_one_survey_per_account`,
  `test_unregistered_character_gets_mail`, `test_cspa_falls_back_to_discord`, `test_no_discord_marks_not_delivered`,
  `test_reason_locked_after_invite`, `test_token_expires_after_30_days`.
- [ ] **Steps 2–4: Run, implement, pass.**
- [ ] **Step 5: Commit** `Send exit surveys (#3198)`.

### Task 4.4: The survey page

```text
Create: backend/surveys/endpoints/exit.py (GET and POST /api/surveys/exit/{token}, one module each if the
        endpoints package needs it), schemas
Create: frontend/app/src/pages/exit-survey/[token].astro, frontend/app/src/pages/partials/exit_survey_component.astro,
        frontend/app/src/components/blocks/exit_survey/ (form, thanks, expired), story + fixtures
Modify: i18n, types, a helper in frontend/app/src/helpers/api.minmatar.org/
Regenerate: openapi.json, api.d.ts
Test:   backend/surveys/tests/test_exit_endpoints.py, frontend story play() tests
```

**Interfaces:**
- `GET /api/surveys/exit/{token}` → 200 `ExitSurveyFormResponse` (corporation name and logo ID, character name,
  member from/to, kind, new corporation name for moves, questions); 410 for a used or expired token; 404 for a bad
  one. No auth.
- `POST /api/surveys/exit/{token}` body `{answers: {question_key: value}}` → 201; 400 with the missing required keys;
  410 when used or expired. Stores the response and sets `responded_at` in one transaction.
- The page follows `frontend/app/src/pages/fleets/rsvp/[token].astro`: `GuestsViewport`, `robots="noindex, nofollow"`,
  `analytics={false}`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`. Questions render with
  `SurveyField`. The thanks and expired states use the design 07 copy.

- [ ] **Step 1: Failing tests:** `test_form_for_valid_token`, `test_used_token_is_410`, `test_expired_token_is_410`,
  `test_submit_once`, `test_missing_rating_is_400`; stories `Exit`, `AllianceMove`, `Expired`.
- [ ] **Steps 2–4: Run, implement, regenerate, pass; open the page from a real token on the dev stack, at desktop
  width and 390px.**
- [ ] **Step 5: Commit** `The exit survey page (#3198)`, run both reviews and open Part 4's pull request with
  screenshots, `Closes #3198` if Parts 1–3 are merged.

---

## Open questions

These change the build, so they're settled in review before the part that needs them:

1. **Executor only** (Part 4): survey admin visible only to `executor_user_id()`, with read access otherwise only
   through Metabase. Should other superusers be kept out too, as planned?
2. **Time in corp on the Departures tab** (Part 2): keep `months_in_corporation`, or does it count as the activity
   data the issue leaves out?
3. **Clearing flags** (Part 2): the current CEO of the corporation that set it, and admins (planned), or admins only?
4. **Replies to the survey mail** (Part 4): mail from the Executor's character as the issue says; should it say
   "don't reply"?
5. **Survey wording** (Part 4): the issue's drafts, fixed as definition version 1 when Part 4 merges.
