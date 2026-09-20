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

## 2026-09-20 — Fishermen bot kicked FL33T people

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Reconciler kicked everyone in the secondary guild
  who held Minmatar Fleet Alliance and did not have a seat. That role is
  shared with FL33T guests; exclusive access is Fisherman. Seats went
  `present` → `pending_join` (unknown member) after the kick.
**Durable rule:** Never guild-scan-kick on a shared role. Dump
  `member_role_id` vs Discord role names and seat statuses first.
**Skill update:** fishermen stray-kick / Alliance-vs-Fisherman row.

## 2026-09-18 — Buyback Match stock extra ores + non-100 lots

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Pasting compressed ore into Match stock added other
  ore families and leftover hangar amounts like 11231. Leftover ore was
  converted to mineral demand, then filled from any hangar ore. Compressed
  picks were not floored to the 100-unit reprocess batch.
**Durable rule:** Ore paste stays in-family. Floor compressed qty to
  `ORE_BATCH_SIZE`. Mineral paste still converts to ore.
**Skill update:** Match stock failure-class row.

## 2026-09-18 — No voice / no Discord roles after site auth

**Category:** pulse.technology
**Verdict:** bug (missing primary) + clarify (Guest)
**Discord:** fix + PR URL for the sole-character heal; clarify Guest
**PR:** fix+skill
**Symptom vs cause:** Voice needs the Alliance Discord role. That role
  comes from `UserAffiliation`, which requires a primary character.
  `EvePlayer` can exist with `primary_character` null while a FL33T
  character is already linked (`Corp <TICKER>` present, no Alliance).
  A Guest with a non-FL33T/BUILD main is expected.
**Durable rule:** Dump `EvePlayer.primary_character` before blaming
  Discord. Affiliation sync sets a main when there is exactly one
  character.
**Skill update:** authed-but-no-roles row.

## 2026-09-18 — Recruiter group required to see applications

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** Applications page needs `Corp <TICKER> Recruiter`
  (ESI Personnel_Manager). Generic Corporation Director / Basic ESI is
  not that group. Empty corp recruiter/director M2M means ESI roles
  have not listed anyone.
**Durable rule:** Dump `user.groups` vs `corporation.recruiters`. Role
  name ≠ Django perm.
**Skill update:** recruiter-vs-director applications row.

## 2026-09-18 — Tribe green tick is OR across requirement blocks

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** A group can be green without Black Ops / JDC if
  another requirement block is met (e.g. Covert Ops + cyno). Multiple
  `TribeGroupRequirement` rows OR; skills inside one row AND.
**Durable rule:** Dump the group’s requirement rows before treating a
  green tick as a skillset bug.
**Skill update:** tribe green-tick OR row.

## 2026-09-18 — Wiki /en/ prefix and archived tech thread

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** thread gone; body still used
**PR:** skill-only (same PR) + drop `/en/` from site wiki links
**Symptom vs cause:** Onboarding URL with `/en/` times out; wiki hosting
  can also hang. BUILD mains are already covered by `FL33T_MEMBER_ALLIANCE_IDS`
  on origin/main. Associates can apply to supply tribe groups on the
  tribe pages (token/skill gates still apply).
**Durable rule:** Open `HelpTicket` row with a missing Discord thread is
  still a ticket. Do not use `/en/` on wiki.minmatar.org links.
**Skill update:** wiki `/en/` row; archived-thread row.

## 2026-09-14 — External guild nicks are `[FL33T] Primary`

**Category:** pulse.fishermen
**Verdict:** bug (missing nick sync) after needs-decision
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Tribe guild seats stored the FL33T nick but never
  PATCHed the secondary guild. Decision: `[FL33T] Primary Character Name`,
  including people already in the tribe.
**Durable rule:** `apply_seat` sets that nick; reconciler backfills
  present seats. Main Discord stays `[TICKER] Name`.
**Skill update:** fishermen nickname row now describes the PATCH, not
  “tag Bear first.”

## 2026-09-14 — Open #help batch (no thread URLs)

**Category:** mixed (mostly pulse.technology)
**Verdict:** mixed (one bug, several needs-decision, two ops skip)
**Discord:** per-thread 1/2/3; skipped assignee-handled non-Pulse
**PR:** fix+skill
**Symptom vs cause:** User said “each discord thread” with no URLs.
  Ingest is `#help` active threads + open `HelpTicket` rows.
**Durable rule:** No URL → list open help tickets. Do not hijack LP/BUILD
  assignee threads. Do not ping the decision owner on their note-to-self.
  Do not re-ask a product question they already answered in-thread.
**Skill update:** ingest “no URL” path; skip/hijack/re-ask rules.

## 2026-09-14 — BUILD main still flagged MAIN_NOT_IN_FL33T

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Troubleshooting banner on a BUILD (Associates)
  main. Skill claimed `FL33T_MEMBER_ALLIANCE_IDS` included Associates;
  origin/main still compared `!=` Alliance only. Associates ticker is
  BUILD — same alliance as M-EXC.
**Durable rule:** Dump primary `alliance_id` + ticker. Associates = BUILD.
  Grep origin/main for the constant; do not trust the skill row alone.
**Skill update:** rewrote the banner row; Associates ticker called out.

## 2026-09-14 — PTT off in fleet voice

**Category:** pulse.technology
**Verdict:** needs-decision
**Discord:** tagged decision owner
**PR:** skill-only (same PR as banner fix)
**Symptom vs cause:** Asked for push-to-talk off in fleet channels.
  That is Discord Use Voice Activity, not a site group.
**Durable rule:** Dump `user.groups` (FC etc.), then tag BearThatCares.
  Do not edit channel overwrites without that call.
**Skill update:** PTT failure-class row.

## 2026-09-14 — Fishermen nicknames to in-game main

**Category:** pulse.technology
**Verdict:** needs-decision
**Discord:** tagged decision owner
**PR:** skill-only (same PR)
**Symptom vs cause:** Wanted the fishermen bot to nick joiners to their
  in-game main. FL33T already syncs `[TICKER] CharacterName`; secondary
  guild seats store that nick but do not PATCH fishermen.
**Durable rule:** Tag BearThatCares before adding secondary-guild nick
  sync. Invite DM is a different path.
**Skill update:** fishermen nickname row.

## 2026-09-14 — Fittings list icons too large

**Category:** pulse.technology
**Verdict:** needs-decision
**Discord:** tagged decision owner
**PR:** skill-only (same PR)
**Symptom vs cause:** Wanted smaller fittings-page icons to scan faster.
  `FittingCard` renders `ItemPicture` at 256.
**Durable rule:** UX product call, not a 403. Ask denser cards vs list
  mode.
**Skill update:** fittings-icon row.

## 2026-09-14 — Mining hulls missing from industry orders

**Category:** pulse.technology
**Verdict:** needs-decision
**Discord:** tagged decision owner
**PR:** skill-only (same PR)
**Symptom vs cause:** Wanted Covetor/Retriever/Porpoise (and later
  Guardian) on the order page. Those EveTypes have no `IndustryProduct`
  row; combat/capital/minerals do.
**Durable rule:** Dump `IndustryProduct` for the hull. Catalog config;
  tag BearThatCares for hulls + strategy.
**Skill update:** missing-order-hull row.

## 2026-09-13 — Tribe approve sent no secondary Discord invite DM

**Category:** pulse.fishermen
**Verdict:** bug
**Discord:** n/a (Cursor report, not a #help thread)
**PR:** fix+skill
**Symptom vs cause:** Chief approved a tribe-group application and the
applicant never got a Discord join DM. Schema for
`TribeExternalGuild` was deployed but no binding row existed, so
`on_membership_became_active` returned immediately. The chief apply-DM
is a separate helper and still worked.
**Durable rule:** Invite-DM missing after tribe approve → dump
`TribeExternalGuild` for that `TribeGroup.code` and seats. Empty
binding is a no-op. Reconciler now seeds Fishermen and backfills seats.
**Skill update:** known-failure row for secondary-guild invite DMs.

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
