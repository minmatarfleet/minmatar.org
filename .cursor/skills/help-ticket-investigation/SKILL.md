---
name: help-ticket-investigation
description: >-
  Investigate #help Discord tickets, pull ticket body plus thread replies
  and screenshots, then reply in the thread (clarify, fix, or tag the
  decision owner) and open a PR with the fix and skill updates. Use when
  the user pastes a discord.com/channels help-ticket URL, asks to
  investigate a bug report in a Discord thread, mentions a
  pulse-technology / help ticket thread, or says to run the help ticket
  investigation loop.
---

# Help ticket investigation

Private Discord threads from the **#help** panel (`HelpTicket`). Pull the
full ticket, then finish in the **thread** with one of the three outcomes
below (1+3 or 2+3 when mixed). Every run also **opens a PR** (product
fix if any, plus skill updates). Do not stop in this chat instead of
Discord.

These files are **public**. Never write ticket-opener names, character
names, snowflakes, thread URLs, ticket ids, user pks, ticket-body quotes,
or screenshot contents into `SKILL.md` or [learnings.md](learnings.md).
BearThatCares stays in this file as the **decision ping target** only —
never paste their Discord id.

**This is an agent skill first.** Durable judgment lives here. Read
[learnings.md](learnings.md) **before** investigating. After **every**
ticket, append a scrubbed learning **and** fold any new rule back into
this file (see §4).

Also read [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
for prod reads. Do not SSH to prod. Use
[production-command](../production-command/SKILL.md) only if you need a
copy-paste kickoff for the user.

## Outcomes (pick one in Discord)

Reply in the **ticket thread**. Do not wait to be asked. Do not leave the
reporter hanging in this Cursor chat.

1. **Clarify existing behavior** — expected permission, how a flow works,
   pending vs active, “not a bug.” Explain it to the opener in the thread.
2. **Fix a real bug** — change this repo, tests, **PR URL in the thread**,
   what happens after deploy.
3. **Tag BearThatCares** — only for an **actual decision** this agent
   cannot make from code (policy, product intent, People/CEO call). Ping
   them in the thread with the question and the facts. Look up their
   Discord user id from `production_readonly` (`DiscordUser`); never
   hardcode a snowflake in these files.

If a ticket is mixed (bug + policy), do **2** for the bug and **3** for
the decision in the same thread reply.

Do not use **3** for “please explain this screen” or expected denials —
that is **1**. Do not use **1** when the code is wrong — that is **2**.

**Always open a PR** before ending: stash unrelated dirty files, branch
from latest `origin/main`, commit the product fix (if any) **and** the
skill/learnings updates, then `gh pr create`. Skill-only PRs are required
when the Discord outcome was 1 or 3. Never skip the PR.

## Task progress

```
Task Progress:
- [ ] Ingest: Discord thread + HelpTicket row + screenshots
- [ ] Read learnings.md for similar tickets
- [ ] Reproduce with code + production_readonly (never write)
- [ ] Verdict: clarify | bug | needs-decision
- [ ] If bug: implement the fix + tests
- [ ] Record + refine: scrubbed learnings.md entry AND update SKILL.md
- [ ] PR from origin/main: fix (if any) + skill updates
- [ ] Discord: outcome 1, 2 (with PR URL), or 3 (tag BearThatCares)
```

---

## 1. Ingest the thread

URL shape: `https://discord.com/channels/<guild_id>/<thread_id>`

- Last path segment is `HelpTicket.thread_id`.
- Thread names look like `<category-code>-<opener-name>`. These are help
  tickets, not Sentry.

### Discord MCP

Use the workspace Discord MCP (`get_channel_info`, `read_messages`,
`get_attachment`, `send_message`). If one Discord MCP times out, try the
other connected Discord MCP.

1. `get_channel_info` `{ channelId }` — confirm name / private thread.
2. `read_messages` `{ channelId, count: "50" }` (raise if the thread is busy).
3. For **every** message id, `get_attachment` `{ channelId, messageId }`.
4. If attachments return CDN URLs, download and **Read the image files**.
   Do not skip “empty” starter messages.

**Embeds are often invisible to MCP.** Starter posts look like empty content
plus a mention ping (assignees). That is **not** the ticket body.

### Ticket body (source of truth)

From `backend/` with `pipenv run python manage.py shell`:

```python
from help_tickets.models import HelpTicket

ticket = (
    HelpTicket.objects.using("production_readonly")
    .filter(thread_id=THREAD_ID)
    .select_related("category", "opener")
    .first()
)
# ticket.body, status, opener, category.code, category.title, opened_at
```

If no row: still use Discord text/screenshots; note the gap.

Follow-up **replies** show up in `read_messages`. Include them. The starter
still needs `HelpTicket.body`.

### Screenshots

- MCP `get_attachment` is metadata/URLs, not always inline pixels.
- Save to a temp path and `Read` the image so vision applies.
- A 403 page is often `HTTP_403_Forbidden()` (“Docking request denied!”)
  from an Astro guard on a Django permission.

### Mentions in Discord

`get_user_id_by_name` often misses people. Resolve Discord user ids from
`HelpTicket` (opener) and `DiscordUser` on `production_readonly` (opener
and, for outcome 3, BearThatCares). Never copy those ids into these
skill files.

---

## 2. Reproduce

1. Restate the reporter’s claim in one sentence.
2. Identify **who is affected** (opener vs someone they are advocating for).
3. Check **prod state** for that account only: groups, `UserAffiliation`,
   `UserCommunityStatus`, corp recruiter/director M2M, Django `has_perm`,
   PilotFeatures (`can_use_feature`), primary `alliance_id`,
   `TribeGroupMembership` (+ history) when the ticket is about tribes.
4. Trace **code**: frontend page guards, Ninja routers, group sync.
5. Match against **Known failure classes** below and [learnings.md](learnings.md).

Do not dump other members’ rows. Do not write through `production_readonly`.
Local Discord bot calls hit the **dev** guild and 404 production members —
do not treat that as “user not in Discord.”

**Wrong working tree:** stash leftover files, `git fetch origin main`, new
branch. The PR commit set is the ticket fix (if any) plus these skill
files — nothing else.

---

## 3. Classify and act

### Known failure classes

Scan this table before inventing a new theory.

| Reporter says | Check first |
|---------------|-------------|
| Site 403 / “Docking request denied” | Django `has_perm` vs Discord/auth **group**. A Corp Recruiter **role** is not the perm an Astro page checks. Associate recruiters are not Alliance; Alliance recruiter groups do not automatically cover them. |
| External button / “Open” reloads the same page | Leaving-site dialog: Open is `x-bind:href="alert_dialog_accept_href"`; `show_alert_dialog` can clear that href in the same click → `href=""` reloads. Not the remote site. Persist-checkbox lives on the dialog; the next Open can still race. |
| Learning / page progress stuck ~80% | `UserPageProgress` / `UserPageSectionProgress` often n−1 (last `resources` / `additional-resources`). Mark-as-read only after every section dwell. |
| UI “roles” plus a query string | Character tags (`/account/tags/`) or ESI `token_type=`, not Discord roles. |
| “Main is not a FL33T member” banner | `MAIN_NOT_IN_FL33T` in `build_character_response` when primary `alliance_id` ∉ `FL33T_MEMBER_ALLIANCE_IDS`. That set includes **Associates**. Do not tell Associates to add an Alliance main. |
| Wrong doctrine behind a hull chip | Capital guides (`CapitalGuideMetaBlocks`) must use `primary_fitting_for_ship` / `fit_match`, **not** `fittings[0]` (lowest id). “Passive” often means Buffer. Dump `EveFitting` for that `ship_id` on `production_readonly`. Local Astro often has an empty fittings API — use production HTML or unit tests with real names. |
| Tribe Actions “wack” / Discord channel missing | **Withdraw** = pending or active (cancel/leave), not a broken menu. Auth/Discord roles (`Tribe Group - …`) sync on **active** only. Each group is a separate apply. Channel list ≠ site membership (overwrites can leak). Dump `TribeGroupMembership` + history before blaming Discord. |
| Corp Discord role looked right, then the **previous** ticker came back | ESI `/characters/affiliation/` and public character data often still report the **old** corp after a join. Bulk `update_character_affilliations` can overwrite `corporation_id`; corporation **history** is usually current first. `Corp <TICKER>` groups sync on `sync_eve_corporation_groups` (different beat). Refresh-Discord-roles should recompute `sync_user_corporation_groups` then `sync_discord_user`. Dump primary `corporation_id`, latest two `corporation_history` rows, `user.groups` `Corp *`, and `DiscordRole.name` (display name may lag a Django group rename). |

### Discord reply

`send_message` on the **thread** `channelId`. Short, operational. No user
pks, no other members’ data, no tokens.

| Outcome | Thread message |
|---------|----------------|
| **1 Clarify** | What the product already does and why. Mention the opener. |
| **2 Fix** | What was wrong, **PR URL**, what happens after deploy. Mention the opener. If you already replied without a PR, follow up with the link. |
| **3 Decision** | Facts + the exact question. Mention the opener **and** BearThatCares. Do not invent a policy answer. |

### PR (always)

- Stash unrelated dirty files. `git fetch origin main`. New focused branch.
- Product fix (outcome 2): tests with
  `pipenv run python manage.py test … --settings=app.settings_test` from
  `backend/`. Frontend: `npm run check` / `npm run test` when UI changes.
- Always include the §4 skill/learnings edits in the same PR.
- Open the PR (summary + test plan). Skill-only is fine for 1 and 3.
- Do not end the run without a PR URL.

---

## 4. After every ticket: record and refine

Mandatory, including clarify and needs-decision. Do this **before**
opening the PR. Do not skip because the fix was “obvious.”

### 4a. Scrub

Nothing identifying goes in these files. Strip before writing:

- Ticket-opener / character names (BearThatCares is the decision-ping
  exception in SKILL.md only — still never their snowflake)
- Other Discord usernames and display names
- Discord snowflakes (guild, channel, thread, user, message)
- Thread URLs, ticket numeric ids, Django user pks
- Ticket-body quotes and screenshot contents
- Personal corp-join / interview stories (write “a member moved corp”)
- Tokens, secrets, webhook URLs, env values

Keep: symptom class, code paths, model/permission names, verdict
(clarify / bug / needs-decision).

### 4b. Append [learnings.md](learnings.md)

Newest first. Use that file’s template. One short entry per ticket.

### 4c. Refine this `SKILL.md`

Ask: would the **next** agent miss this if they only read this file?

| Situation | Edit |
|-----------|------|
| New failure class | Add a row to **Known failure classes** |
| Workflow miss (no PR, Discord reply only in this chat, dirty branch, skipped `HelpTicket.body`) | Tighten the checklist or Outcomes |
| Existing row is wrong or incomplete | Rewrite that row; do not add a duplicate |
| Bug is fixed and the old heuristic now misleads | Update the row so it describes the **current** check, not the old bug |
| One-off, no reusable rule | Learnings entry only; do not grow this file |

Do not paste tickets into this file. Keep it under 500 lines. If a row
rots, delete it.

### 4d. Commit and open the PR

Same branch as the product fix (or skill-only if there was no fix).
Include `SKILL.md` and `learnings.md`. Then open the PR. The run is not
done until that PR exists.

---

## What belongs where

| Put in learnings.md / this file | Do not bake in |
|---------------------------------|----------------|
| MCP embed gap → always load `HelpTicket.body` | Discord REST wrappers, bot tokens |
| Permission / affiliation / ESI-lag gotchas | Discord user ids, guild ids |
| Hull-chip / dialog-race / progress-% classes | Full ticket dumps |
| Associates vs `MAIN_NOT_IN_FL33T` | Channel overwrite archaeology |
| Tribe pending vs Discord role timing | Prod Discord REST from a local bot token |

## Additional resources

- [learnings.md](learnings.md)
- [debug-production-readonly-db](../debug-production-readonly-db/SKILL.md)
