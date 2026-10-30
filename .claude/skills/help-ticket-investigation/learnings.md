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

## 2026-10-30 — Old buyback sales stay open after the contract finishes

**Category:** pulse.technology (buyback forum; no HelpTicket row)
**Verdict:** bug
**Discord:** no reply (forum channel, not a help thread; cloud bot 403s the production guild)
**PR:** fix+skill
**Symptom vs cause:** Pending hangar sales stayed open after a finished item-exchange to the buyer's corporation. Another corp's contract sync stored that `contract_id` under itself, and the ledger sync only read rows whose corporation FK was still M-EXC, so no `sold_contract` row existed to auto-complete the order.
**Durable rule:** Match M-EXC in/out contracts by `assignee_id` and `issuer_corporation_id`. The corporation FK is whoever synced last. A corp assignee still counts as the buyer when one of their characters is in that corp.
**Skill update:** added the buyback sale-threads row.

## 2026-10-25 — Structure-pings channel mislabels orbitals and drops reinforce

**Category:** pulse.technology (structure-pings channel; no HelpTicket row)
**Verdict:** bug
**Discord:** no reply (not a help thread; test-guild bot 403s the production guild)
**PR:** fix+skill
**Symptom vs cause:** An orbital attack posted as a skyhook with the raw notification body. The reinforce, and earlier shield/armor/destroyed stages, stayed `discord_success` false because `is_new_event` treated any second event on that structure inside an hour as a duplicate.
**Durable rule:** That channel URL is not a HelpTicket. Escalations still ping inside the hour. Name the orbital from `typeID`. Do not post the investigation into the channel.
**Skill update:** added the structure-pings row.

## 2026-10-17 — Previous corp Discord role stays after the main moves

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only
**Symptom vs cause:** Main moved corp and the old corp Discord role kept returning. Primary `corporation_id` already matched ESI and the latest history row. Another linked character is still in the previous corporation, and member groups include every linked character.
**Durable rule:** Dump every linked character's corporation, not only the primary. Refresh re-adds `Corp <TICKER>` while any character remains in that corp. Nickname follows the primary.
**Skill update:** added the alt-still-in-previous-corp row next to the ESI-lag row.

## 2026-10-15 — Campaign page 403 for alliance members

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Logged-in alliance members got the site 403 on a campaign link. The page checks `campaigns.view_campaign`, which is not on the Alliance group. `campaigns.view` is affiliation-scoped and the PilotFeature row was missing because startup never ran `sync_pilot_features`.
**Durable rule:** Campaign view is Alliance, Militia, and Associate via the feature. Profile permissions must list `campaigns.view_campaign` when that wiring passes. Sync features after migrate.
**Skill update:** added the campaign-page 403 row.

## 2026-10-14 — Discord login notice Continue does nothing

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Continue on the Discord account notice did nothing after the checkbox was clicked, on several browsers. The button stayed disabled until Alpine loaded from jsDelivr, and the click handler returned silently when the checkbox model was false.
**Durable rule:** Login notice is a native GET form with a required checkbox. Keep `redirect_url` in a hidden field. `HelpTicket.opener` stays null until that login completes.
**Skill update:** added the Discord login notice row.

## 2026-10-13 — Grade ore stock ignored on the build planner

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Pasting on-hand ore into the build planner only exact-matched names. II/III/IV-Grade and Brimful/Glistening stacks are not the compressed base the shopping list buys, so their minerals stayed on the buyback purchase. Fill also refined grade ore as the base family.
**Durable rule:** Credit variant ore from TypeMaterials before sizing the compressed buy. Fallback scale is 1.05/1.10/1.15 and Brimful 1.15 / Glistening 2. Leave exact `Compressed {base}` for the 1:1 pass.
**Skill update:** added the planner grade-ore row.

## 2026-10-13 — Fleet MOTD reload steps and guide link

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** The new-player guide said to read the fleet MOTD and not how to bring it back after fleet chat scrolls it off. Generated MOTD Resources listed bookmarks, broadcast, and channels, with no guide link. Discord fleet pings already link the same page.
**Durable rule:** Reload is fleet chat → three dots → Reload Channel's MOTD. The in-game guide line is `SECTION_RESOURCES_GUIDE` and must use `<loc>`.
**Skill update:** added the MOTD reload / guide-link row.

## 2026-10-13 — Veldspar skipped on pyerite-heavy buyback orders

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** A large Veldspar hangar was barely used when mineral orders had more Pyerite than Tritanium. Fill covered the largest mineral first, so Scordite satisfied Tritanium as a byproduct. Water stays off the allowlist via `PAUSED_ACCEPTED_TYPE_NAMES` so the weekly seed cannot turn it back on.
**Durable rule:** Cover Tritanium from Veldspar while any Veldspar-family ore is on hand, then the other minerals. Paused accepted names stay `active=False` across seed. Hangar sales of stock already on hand are separate from the allowlist.
**Skill update:** added the Veldspar-first row and the paused-allowlist row.

## 2026-10-13 — Fishermen cleanup DMs every reconcile

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Group chief got a cleanup-failed DM every reconcile. An unentitled seat kick returned 403 (member still in the guild; bot cannot kick). The alert channel post also 403s, so the fallback is a chief DM. `failure_count >= 3` alerted again on every later run.
**Durable rule:** Alert once when status first becomes `cleanup_failed`. Kick 403 is still-in-guild plus missing permission, not a leave. 404 marks `removed`. Channel 403 falls back to the chief DM.
**Skill update:** added the repeating-cleanup-DM row.

## 2026-10-10 — No Discord roles, site account never created

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only
**Symptom vs cause:** Waited hours in Discord and still had no roles. No `DiscordUser` for that account, so `HelpTicket.opener` is null and role sync has nothing to push.
**Durable rule:** Missing `DiscordUser` means they have not logged in on the site. Waiting does not grant roles. If the row exists, use the authed-but-no-roles checks.
**Skill update:** added the unlinked-account row above the authed-but-no-roles row.

## 2026-09-30 — Hidden tribe-group roster

**Category:** pulse.technology
**Verdict:** bug (product decision, then implement)
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** A group roster listed primary characters to every alliance member. Decision: a per-group flag. Members and managers see names; everyone else sees a count of blurred placeholders.
**Durable rule:** `TribeGroup.roster_hidden`. Do not return names in the roster, showcase, or group-chief payload for viewers who fail `user_can_view_group_roster`.
**Skill update:** rewrote the hide-roster row.

## 2026-09-30 — Open technology threads (batch)

**Category:** pulse.technology
**Verdict:** mixed (two bugs, one small copy fix, several clarify, one needs-decision)
**Discord:** per-thread; two archived threads had no reply
**PR:** fix+skill
**Symptom vs cause:** Match stock refused hangar ore because sellable qty was contract-ledger net, not the hangar snapshot. Combat-log Submit reloaded the page because the form is teleported and htmx never bound it. Purchase confirm named the pilot and not the structure.
**Durable rule:** Listed buyback stock is the hangar snapshot minus later sales and pending holds. Teleported htmx forms need `htmx.process`. Archived help threads and note-to-self tickets get no Discord ping.
**Skill update:** stock-vs-fill row, combat-log teleport row, reapply / planner / contract location / roster / fitting-paste rows.

## 2026-09-30 — Buyback purchase contract location

**Category:** pulse.technology
**Verdict:** bug (missing location on the buy flow)
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Buying from stock said who to contract, not where. Sell copy already says Amo. Confirm now uses buyback settings location.
**Durable rule:** Purchase confirm reads `settings.location`. Stockpile structure id is separate from the display location.
**Skill update:** contract-where row.

## 2026-09-30 — Listed ore missing from Match stock

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Stock page showed the hangar quantity. Match stock sold only inbound-minus-outbound contracts, so the rest was “Not in hangar.”
**Durable rule:** With a snapshot, sell the snapshot minus sales after `taken_at` and pending. Do not add inbound on top of the snapshot.
**Skill update:** stock-vs-fill row.

## 2026-09-30 — Combat log submit shows no analysis

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Submit left the empty “no stored combat log” list. The form lives in an `x-teleport` template, so htmx did not handle it and the browser POSTed the page. The log itself parses.
**Durable rule:** `htmx.process` teleported forms. Zero stored rows means the API was not called.
**Skill update:** combat-log row.

## 2026-09-30 — Old Discord application thread blocks a new app

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** A years-old application thread is read-only. Creating an application on the site does not check that thread.
**Durable rule:** Locked Discord application thread ≠ a site block. Apply on `/alliance/corporations/`.
**Skill update:** reapply row.

## 2026-09-30 — Build planner capital cost far below in-game

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** Resbroko is priced with a hardcoded −50% faction-warfare system bonus. In-game at 0% the job cost is higher. Decision already in-thread: price upgraded systems, no planner slider.
**Durable rule:** Hydra systems use `HYDRA_FW_SYSTEM_COST_BONUS`. Do not re-ask.
**Skill update:** planner bonus row.

## 2026-09-30 — Fishermen names visible on the site

**Category:** pulse.technology
**Verdict:** needs-decision
**Discord:** tagged decision owner
**PR:** skill-only (same PR)
**Symptom vs cause:** Request to hide Fishermen members on the site. Group roster is public primary characters.
**Durable rule:** Anonymity is a policy call. Tag the decision owner. Do not hide the roster first.
**Skill update:** roster privacy row.

## 2026-09-30 — Buyback order extras (shortfall history, reports, freighter)

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** Three enhancements: keep unmatched lines on the order, a mineral in/out report, and a freighter handoff. Match-time shortfall already exists and is not stored. No report and no freighter prefill. Already routed in-thread; not re-asked.
**Durable rule:** Unfulfilled paste lines are the fill shortfall, not a failed order. Do not re-ask a product question already handed to implementation.
**Skill update:** none (already covered by “do not re-ask”)

## 2026-09-30 — Paste a fit into fitting orders

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** Create fitting order only accepts site `fitting_id` values. Someone in-thread already took the paste-your-own-fit request.
**Durable rule:** Confirm the gap. Do not re-ask or start a second implementation.
**Skill update:** fitting-paste row.

## 2026-09-30 — Archived onboarding ticket and note-to-self

**Category:** pulse.technology
**Verdict:** clarify (already handled) / skip
**Discord:** threads gone; no reply
**PR:** skill-only (same PR)
**Symptom vs cause:** One onboarding ticket was already explained (wiki `/en/`, BUILD mains). One note-to-self has no thread. Neither gets a new Discord message.
**Durable rule:** Missing thread → no invented reply. Do not ping the decision owner on their own note.
**Skill update:** none (already covered)

---

## 2026-09-24 — SRP warning with no reason

**Category:** pulse.technology
**Verdict:** bug (blank error) + clarify (character not on account)
**Discord:** fix + PR URL, plus why the killmail was rejected
**PR:** fix+skill
**Symptom vs cause:** SRP wizard showed a warning and the retry buttons
  with no text. Resolve returned 403 because the victim
  `EveCharacter.user` was null. The partial rendered an unused
  `endpoint_error` instead of `fetching_error`. The hull was already on
  `ShipReimbursementProgram`.
**Durable rule:** A blank SRP warning is a swallowed resolve error.
  Dump the victim character’s `user_id` before treating the hull as
  uncovered.
**Skill update:** SRP blank-warning row.

## 2026-09-20 — Fishermen bot kicked FL33T people

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** A guild-scan kicked anyone holding Minmatar Fleet
  Alliance without a seat. That role is the correct grant for entitled
  seats, not a kick filter. Dev bot with Kick on the hardcoded live guild
  did the removals; seats went `present` → `pending_join`.
**Durable rule:** Only kick unentitled seats. Never guild-scan-kick on
  member_role. Fishermen member_role stays Minmatar Fleet Alliance.
**Skill update:** fishermen stray-kick row; Alliance is the grant role.

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
