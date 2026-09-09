# Help ticket learnings

Public-safe log. Newest first. **No secrets, no people, no Discord ids.**

This file is committed to a public repository. Every entry must still be
useful without naming anyone.

## Scrub before writing

Never include:

- Ticket-opener / character names (do not log who was pinged)
- Discord usernames and display names
- Discord snowflakes (guild, channel, thread, user, message)
- Thread URLs, ticket numeric ids, Django user pks
- Ticket-body quotes, screenshot contents
- Personal corp-join or interview stories
- Tokens, secrets, webhook URLs, env values

Keep: date, short title, category code (not ticket id), verdict
(clarify / bug / needs-decision), one-line symptom vs cause, one durable
rule. Every run opens a PR (fix and/or skill updates).

After appending, **fold any new durable rule into [SKILL.md](SKILL.md)**
(Known failure classes or the workflow). If the rule already lives there,
do not duplicate it — one clarifying clause at most.

## Template

```
## YYYY-MM-DD — short title (symptom class, not a person)

**Category:** help-ticket category code (e.g. pulse.technology)
**Verdict:** clarify | bug | needs-decision
**Discord:** clarify to opener | fix + PR URL | tagged decision owner
**PR:** always (fix+skill | skill-only)
**Symptom vs cause:** one or two lines, no names
**Durable rule:** what to try first next time
**Skill update:** what changed in SKILL.md, or “none (already covered)”
```

---

## 2026-09-09 — BUILD alliance BPC packs not on site / claim

**Category:** pulse.technology
**Verdict:** needs-decision (plus clarify: not a bug)
**Discord:** tagged decision owner
**PR:** skill-only
**Symptom vs cause:** Asked to surface BUILD alliance BPC/mineral packs in
industry-order claim and/or on `/industry/blueprints/` or a
`/market/ops/contracts/`-style industrial page. Those pages are hangar
BPC search and doctrine fitting stock. Packs exist as corp ESI contracts
assigned to BUILD; they are not `EveFitting`-matched and the structure
was not an `EveLocation`, so they never hit `EveMarketContract`. Claim is
quantity + blueprints checkbox. 48h cap is `self_assign_maximum`.
**Durable rule:** Alliance industrial packs ≠ ops contracts. Dump
`EveCorporationContract` (`assignee_id` = BUILD) before treating missing
site listings as a sync bug. Product intent before building a new
surface.
**Skill update:** failure-class row; stub `HelpTicket.body` → read replies.

## Seed patterns (anonymized)

These are the classes already encoded in SKILL.md. New tickets append
**above** this heading.

### 2026-09-09 — Corp Discord role bounced to previous ticker

**Category:** pulse.technology
**Verdict:** bug
**PR:** shipped
**Symptom vs cause:** After a corp join, Discord looked right, then the
previous corp ticker came back. Corporation history already had the new
corp; bulk ESI affiliation still returned the old corp and overwrote
`corporation_id`. Corp-group sync then re-applied the old ticker.
Refresh-Discord-roles used to mirror `user.groups` without a per-user
corp-group recompute. `DiscordRole.name` can lag a Django group rename.
**Durable rule:** History over stale ESI. Dump primary `corporation_id`,
latest two `corporation_history` rows, `user.groups` `Corp *`, and
`DiscordRole.name`. Local Discord client is the dev guild.
**Skill update:** failure-class row + “fix means PR from origin/main.”

### 2026-09-09 — External Open reloads the current page

**Category:** pulse.technology
**Verdict:** bug (dialog) + follow-up (page progress) + not-a-bug (roles)
**PR:** shipped
**Symptom vs cause:** Account “authorized third-party apps” (external
link) looped to the same page until “don’t show this anymore.” Open binds
`alert_dialog_accept_href`; `show_alert_dialog` cleared it in the same
click. Learning progress ~84% is often n−1 sections (last `resources`).
UI “roles” + query string is character tags or ESI `token_type=`.
**Durable rule:** Same-page reload on an external button → leaving-site
dialog race, not the remote site. Dump `UserPageProgress` when they
mention a percent.
**Skill update:** dialog-race and progress-% rows.

### 2026-09-09 — Hull chip linked to the wrong doctrine

**Category:** pulse.technology
**Verdict:** bug
**PR:** shipped
**Symptom vs cause:** Capital-guide hull chip opened the Active fit when
the article said to start on Passive/Buffer. Table used `fittings[0]`
(lowest id), not `primary_fitting_for_ship`. Local fittings API is often
empty.
**Durable rule:** Dump `EveFitting` for that `ship_id` on
`production_readonly`. Reproduce hrefs on production or in tests.
**Skill update:** hull-chip row. Empty Discord starter → `HelpTicket.body`.

### 2026-09-09 — Associates banner + tribe apply confusion

**Category:** pulse.technology
**Verdict:** bug (banner) + not-a-bug (tribe Actions / Discord)
**PR:** none
**Symptom vs cause:** Troubleshooting banner said the main was not a
FL33T member while the primary was in Associates. `MAIN_NOT_IN_FL33T`
used to check Alliance only. Tribe Withdraw was a **pending** apply;
other tribe groups are separate applies; Discord tribe roles sync on
**active**.
**Durable rule:** `FL33T_MEMBER_ALLIANCE_IDS` includes Associates. Dump
`TribeGroupMembership` + history before blaming Discord. Mention openers
from prod Discord ids, not `get_user_id_by_name`.
**Skill update:** banner + tribe rows; mention rule.

### 2026-09-09 — Associate recruiter 403 on applications

**Category:** pulse.technology
**Verdict:** bug
**PR:** shipped
**Symptom vs cause:** Associate corp recruiter could interview in Discord
but the applications page 403ed. Alliance recruiters get the Django perm
via Alliance / alliance-corp Recruiter groups. The associate Corp
Recruiter **role** had no Django permission the Astro guard checks.
**Durable rule:** For site 403s, compare `user.groups`, affiliation, and
`has_perm` — Discord/auth role ≠ the perm the page checks. MCP starter
was empty; body was in `HelpTicket`.
**Skill update:** 403 row; always load `HelpTicket.body`.
