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

## 2026-11-26 — Rejoined the academy, no corp role and a `[?]` nickname

**Category:** pulse.technology
**Verdict:** bug
**Discord:** reply with PR link
**PR:** fix+skill
**Symptom vs cause:** A pilot back in a corp they had left for an NPC corp long ago got no corp Discord role after refreshing. Public ESI affiliation had the corp; the cached corporation history still ended on the NPC corp. The stale-ESI guard read "ESI equals the previous history row" as stale ESI and stored the NPC corp, so the nickname showed `[?]`.
**Durable rule:** A history row only beats ESI when the join is recent (ESI affiliation catches up within hours). Check both public routes when roles are missing after a rejoin. The production DB was not reachable this run; the diagnosis came from public ESI and the Discord member record.
**Skill update:** new rejoin row; the Trial row now names the window.

## 2026-11-24 — Mentor feature requests, plus "at least an hour" on Change time

**Category:** pulse.technology
**Verdict:** needs-decision (user feedback issues)
**Discord:** issue links in the thread
**PR:** skill-only
**Symptom vs cause:** One ticket carried three asks across follow-ups: a calendar invite on the booked-class DM, Minmatar standings on Corporation Health, and (with a screenshot) Change time refusing a class 15 minutes out. An earlier run had opened the issue for the first two without replying in the thread. The refusal is `_bookable_start` in `learning/mentors/service.py` (more than one hour and at most 30 days out), shared by accept and reschedule and pinned by a test.
**Durable rule:** Before opening an issue, search for one already opened from the same ticket and reuse it. Read follow-ups posted after the starter: a later message can be a new ask. Opening an issue is not the end of the ticket; the thread reply is.
**Skill update:** extended the booked-mentor row with the lead-time rule; added the reuse-the-issue step.

## 2026-11-24 — Universe structures list empty for an Associate pilot

**Category:** pulse.technology
**Verdict:** needs-decision (user feedback issue)
**Discord:** issue link in the thread
**PR:** skill-only
**Symptom vs cause:** A BUILD-corp pilot (affiliation Associate) reported structures but saw zero on `/universe/#structures`, even their own. `structures.view` defaults to Alliance and Associate, but `visible_structures` shows `visibility=alliance` rows only when the affiliation is exactly Alliance. Every reported row is alliance-wide. An alt in an Alliance corp does not change the account's affiliation.
**Durable rule:** When a page is visible but its list is empty, compare the feature's default affiliations with the row filter in `universe/access.py`. Whether Associates see alliance-wide intel is a product call.
**Skill update:** added the empty-structures row.

## 2026-11-24 — Chief DM for a tribe application has no link

**Category:** pulse.technology
**Verdict:** needs-decision (feature request)
**Discord:** issue link in the thread
**PR:** skill-only
**Symptom vs cause:** A tribe chief asked for a link to the group page in the "New tribe membership application" DM. `_notify_chief_of_new_request` passes no `url`, and the text still says "admin panel". `discord_format` only sets `embed.url` when the embed keeps a title, and it drops the title when `discord_message` already leads with it, so a url alone would not show a link. A link button (`link_button_components`) is the existing helper.
**Durable rule:** Notification links need both a `url` and a rendered title or a link button. Check `discord_format` before promising a clickable link.
**Skill update:** added the chief-DM row.

## 2026-11-24 — Associate-corp sidebar screenshot with an empty ticket body

**Category:** pulse.technology
**Verdict:** clarify (asked for what was expected)
**Discord:** clarify to opener
**PR:** skill-only
**Symptom vs cause:** The starter embed's details were empty and `production_readonly` was not configured in that run, so only a screenshot of a BUILD-corp member's sidebar without Fleets was available. `fleets.view` defaults to Alliance, Militia and Associate (`groups/features/registry.py`); `fleets.create` is Alliance only. Universe is shown to every signed-in pilot.
**Durable rule:** A missing neocom button is a gate (`can(gates, ...)`) backed by a pilot feature's default affiliations. Read the registry before calling it a bug. With no body and no DB, explain the gate and ask what was expected rather than guessing.
**Skill update:** added the neocom-button row.

## 2026-11-24 — Structure report resubmit cannot correct the type

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL in the thread
**PR:** fix+skill
**Symptom vs cause:** A pilot reported a structure with the wrong type, then reported it again with the right type and picked the existing row. `apply_report` updated name, owner, fit and hour on a reported row but never `type_id` / `type_name`, so the wrong type stuck. A row reported without a name is called `<system> - <type>`, so with a blank name and a different type it was not even offered in the match step.
**Durable rule:** A reported row's type is what a pilot picked; a later report on that row corrects it (and renames a default-named row). ESI rows never change type from a report. Match step also offers reported rows that still carry their default name.
**Skill update:** added the structure-report type row.

## 2026-11-22 — Tribe application notice, then nothing on the members page

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL in the thread
**PR:** fix+skill
**Symptom vs cause:** A pilot applied to two tribe groups. Chiefs got the request notification. About 45 minutes later both rows went inactive with reason `removed` and no actor, so the members page no longer listed them. The same second created the account's trial status, which is the Alliance affiliation save. Affiliation sync deletes the previous row before inserting the new one, and offboard ran while the account had no affiliation. There is no limit on how many groups a pilot can apply to. A group with no membership row was never submitted. One group was applied again and approved; the other is still inactive.
**Durable rule:** Pending applications cleared with `reason=removed` and `changed_by` null, in the same second as an affiliation or trial-status write, are this gap. Offboard runs after the affiliation transaction commits. No membership row means that group was never submitted.
**Skill update:** added the tribe-application-notice row.

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

## 2026-11-21 — Booked mentor class time cannot be changed

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL posted in the thread
**PR:** fix+skill
**Symptom vs cause:** After a class is booked, the only time change is the 48-hour "We moved it" answer, which clears the time and returns the request to asked. The mentor can now change the date and time while the class stays booked. Both pilots get a DM, and a new time restarts the 24-hour reminder.
**Durable rule:** Accept books an asked request. `reschedule` moves a booked one. "We moved it" is still the close-out that puts the request back to asked.
**Skill update:** added the booked-class reschedule row.

## 2026-11-21 — Fitting order Save prices reloads with an empty box

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL in the thread
**PR:** fix+skill
**Symptom vs cause:** Pasting purchased prices on a fitting order stayed on the purchase step and the box came back empty. Every to-buy line still had a null unit price. The parser only accepted a tab or a double space with the item name in the first column and a US-formatted number. Multibuy is `Name qty` with one space, wallet rows lead with the date, and EU amounts with an ISK suffix did not parse. A station name like `Jita IV - Moon 4` must not be read as a price.
**Durable rule:** Match order item names inside the line. Accept a single-space quantity and total, wallet rows, and ISK/EU numbers. When nothing matches, keep the paste and say so. The submit button stays inside the form.
**Skill update:** added the fitting-order landed-price row.

## 2026-11-20 — Thread replies after the investigation PRs merged

**Category:** pulse.technology
**Verdict:** two bugs already fixed, one clarify
**Discord:** fix + PR URL in the two bug threads; clarify in the academy thread, including that directors edit Settings
**PR:** skill-only (product PRs already merged)
**Symptom vs cause:** The investigation PRs recorded no Discord reply because that environment's bot is the test guild. The workspace Discord MCP posts in the production help threads. The academy follow-up image is another corporation's Apply tab (ship rules present). The academy still has zero `CorporationRequirement` rows. `can_edit_corporation_settings` is the CEO and directors.
**Durable rule:** After a help-ticket PR merges without a thread reply, post from the workspace Discord MCP and record that the reply landed. A screenshot of green doctrine rows is the recruitment-requirement check. Do not re-ask about the written application question.
**Skill update:** Discord-reply note, and the L3ARN row now names directors and the follow-up screenshot.

## 2026-11-20 — Academy recruitment page shows no ship/doctrine check

**Category:** pulse.technology
**Verdict:** clarify, plus needs-decision on the written question
**Discord:** clarify posted after merge (directors can edit Settings; written question not re-asked)
**PR:** skill-only
**Symptom vs cause:** The academy recruitment page does not show which doctrine ships an applicant can fly, and other corps do. The automatic check is `CorporationRequirement` rows. The academy has none, so the Apply tab is interview topics only. Corps with `ships` rules show the check. Directors add rules under Settings. The written doctrine-ships question on the shared application form was left off the academy form on purpose.
**Durable rule:** Compare `CorporationRequirement` rows before calling the skill check disabled. The written question is a separate, intentional academy-form gap.
**Skill update:** added the L3ARN recruitment skill-check row, and the note to edit `.claude/skills/` then sync.

## 2026-11-20 — Review tasks for other corporations' applications

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL posted after merge
**PR:** fix+skill
**Symptom vs cause:** An alliance member saw review tasks for pending corporation applications, and thought a newly added director-scoped character caused it. The account was not a director or recruiter of any corporation. The Alliance auth group held the application permissions, so `can_review_applications` was true for every member and every corporation. The token did not add a directors or recruiters row.
**Durable rule:** Ignore application permissions that come only from the Alliance group. A non-reviewer still receives their own rows from the application list, because the corporation page uses that list for status. Corp recruiter groups keep the permission.
**Skill update:** added the review-tasks row.

## 2026-11-20 — Mentor class rejects a tribe member (group name vs code)

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL posted after merge
**PR:** fix+skill
**Symptom vs cause:** A published mentor class required a tribe group, and an active member still saw the class locked. The stored value was the group's display name. The check queried `tribe_group.code` only, so the name never matched. Membership is one row per user, including when the character on the roster is an alt. Pending membership still does not qualify.
**Durable rule:** Dump `MentorClass.requirements` before the membership. A `tribe_group` token is a code or a unique group name. Active `TribeGroupMembership` on the account is what counts.
**Skill update:** added the mentor-class tribe requirement row.

## 2026-11-21 — Help ticket thread cuts off a long report

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** A report longer than 1024 characters showed up cut off in the help thread. The modal allows 2000 and the row stores the full body. The starter embed put that body in a field, which Discord caps at 1024, so the rest never appeared. Nothing threw, so Sentry and PostHog had no error.
**Durable rule:** Compare `len(HelpTicket.body)` to 1024 before calling it a modal limit. The thread posts the body as an embed description (4096) and continues in another embed past that.
**Skill update:** added the clipped help-ticket row.

## 2026-11-21 — Reddit post approval looks cut off

**Category:** pulse.technology
**Verdict:** bug, plus a refusal that looks like one
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** A recruitment post looked cut off once it reached approval. The review panel capped the body at 32rem, so the end of a long post sat under a thin scrollbar. The reminder DM that says to post it yourself splits near 2000 characters and stripped the trailing newlines, so the blank line at the split disappeared. A save that hits the profanity list is refused before write; the queue keeps the previous body, and that body can itself end mid-word. The mid-word ending is stored text. The content column is longtext, and the save path does not shorten a body.
**Durable rule:** The review body is not height-capped. Reminder chunks keep their trailing newlines so the fenced pieces join back to the post. Compare `len(content)`, the stored ending, and `find_profanity` before calling a short post a truncation. A profanity refusal leaves the last successful body in the queue.
**Skill update:** added the reddit approval clip row.

## 2026-11-14 — Open technology threads (batch, Discord MCP on production)

**Category:** pulse.technology
**Verdict:** mixed (bug, feature, clarify, note-to-self)
**Discord:** fix or feature + PR URL in each live thread; archived threads got none
**PR:** one fix PR per ticket, plus this skill-only PR
**Symptom vs cause:** The workspace Discord MCP reached the production guild, so replies landed for the first time. A stockpile headline counted the whole hangar while the list excluded pending purchase reservations. A request for EVE names on a corp server hit the role-mapping reconciler, which never set nicknames. Two extra buyback stations were display and data only. An Alts doctrine category and a Fanfest tribe were additive features. Fitting orders gained EFT paste stored on the line. An old associate onboarding ticket was already fixed in code; only production group settings could still block tribe applies. Health lists hard-coded five rows and showed one status button on one tab; the Reddit link error was a missing production setting.
**Durable rule:** Ingest every open thread first; archived ones are “Channel not found” and get no reply. Note-to-self tickets with one line get no PR without the owner's scope. Summary numbers must share the list's function. Check every bot-managed server type for Discord sync gaps.
**Skill update:** MCP note, and rows for stockpile headline, health page size and status buttons, Reddit link setting, buyback locations, corp-server nicknames, doctrine categories, tribe creation, associate tribe apply; fitting-paste row rewritten.

## 2026-11-13 — Buyback sale threads close from Discord buttons

**Category:** pulse.technology (buyback forum; no HelpTicket row)
**Verdict:** bug
**Discord:** no reply (forum channel, not a help thread)
**PR:** fix+skill
**Symptom vs cause:** Pending sale threads stayed open after the in-game contract finished. Auto-complete only runs once `sold_contract` lines cover the order, and that item read was not keeping up with new contracts. The close is now the same shape as LP buyback: coordinators press Contract up, the buyer presses Contract accepted, the thread archives.
**Durable rule:** Do not wait on a full contract match to archive a sale thread. Contract accepted closes a new sale. Threads already open get one Close button for the buyback team and are left out of that sweep. The hourly sweep reminds at 24h, cancels a new sale still waiting on Contract up at 48h after that warning, and only reminds the buyer once the contract is up. Still record contract items. The completion post names lines the synced contract does not cover. The forum is not a HelpTicket.
**Skill update:** rewrote the buyback sale-threads row for the button close.

## 2026-11-13 — Year-in-review cards used placeholder numbers

**Category:** pulse.thinkspeak (named channel; no HelpTicket row)
**Verdict:** clarify
**Discord:** numbers posted in the channel
**PR:** skill-only
**Symptom vs cause:** Logistics, mining, and PvP year cards were placeholder art. Freight m³ and rewards are finished freight contracts. LP is completed buyback sells, and that source does not cover the whole year. Mining m³ for FL33T and BUILD has every day of the calendar year; ore ISK is the current Jita guide and misses unpriced new ores. Reaction runs are delivered ESI activity 9; output units are a different figure (SDE activity 11). Destroyed ships and ISK are zKill for the combat alliance and are down versus the prior year. Site fleets are up.
**Durable rule:** A three-id Discord link is guild/channel/message. No HelpTicket row means answer that channel. Do not put a year-over-year percent on a source with no prior year. Do not add the associate alliance onto zKill destroyed totals.
**Skill update:** added the year-in-review row and the three-id link note.

## 2026-11-11 — Accepted into a corp, then only some Discord access changed

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** no reply (test-guild bot 403s the production help thread)
**PR:** skill-only
**Symptom vs cause:** A new member was accepted into a corporation and then reported that only some permissions rolled back. The account is Trial, which Alliance applies automatically, and the Discord roles still match the site groups (Alliance, the corp role, Trial, timezone brackets). The primary's stored corporation is still the previous one, which is not an `EveCorporation` row, so the `:49` nickname sync wrote `[?]`. Public ESI and affiliation already show the new corporation; corporation history still lists the previous one. Another linked character is in the new corp, so the corp role stayed.
**Durable rule:** Trial plus a `[?]` nickname is this split, not a role-sync bug. The history preference only overrides ESI when it still reports the previous corporation. The next affiliation run should store the new corp and the nickname becomes `[TICKER]`.
**Skill update:** added the partial-rollback row.

## 2026-11-09 — Corporation Apply closes with nothing saved

**Category:** pulse.technology
**Verdict:** bug
**Discord:** explained in the thread before the fix; no further ping
**PR:** fix+skill
**Symptom vs cause:** Apply fired a real submit and no `EveCorporationApplication` was created. The button init stripped `disabled` while the form was already invalid, so Apply stayed clickable. Roles and the confirmation checkboxes are not browser-required, the server rejected that body, and the dialog closed on the click.
**Durable rule:** A corporation Apply submit with no application row is this button. Keep `x-bind:disabled` in charge, require a role and the confirmation checkboxes, and do not close the dialog in the submit handler.
**Skill update:** added the corporation Apply row.

## 2026-11-08 — New ore family stays unstacked on the buyback list

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill
**Symptom vs cause:** Grades of a newly accepted ore rendered as separate rows. Dark Ochre stacked because it is on `BUYBACK_ORE_BASES`. The new family was not, so the display never grouped it. A daily job was requested; the list is what gates the group.
**Durable rule:** Group `category: ore` rows that share `ore_variant_family` when there are two or more. Do not add the name to `BUYBACK_ORE_BASES` just to fix the display; that also changes the weekly seed and the Jita clamp.
**Skill update:** added the unstacked-ore-family row.

## 2026-11-08 — Corporations shortcut opens the alt corporation

**Category:** pulse.technology
**Verdict:** bug
**Discord:** fix + PR URL
**PR:** fix+skill (same PR)
**Symptom vs cause:** The neocom corporation button opened the alphabetically first corporation the pilot leads. They are CEO of the main's corporation and of an alt corporation in BUILD, so the alt name won.
**Durable rule:** `led_corporations[0]` is the main character's corporation when they lead it, then other CEO corporations, then director corporations by name.
**Skill update:** added the corporations-button row.

## 2026-11-08 — Application watched on a screenshare never appears

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** clarify to opener
**PR:** skill-only (same PR)
**Symptom vs cause:** A recruit was watched submitting an application and nothing showed in Discord or on the site. Every pending application from the last two weeks already has a forum thread. No row exists for a submission that failed to post. The ticket does not name the character.
**Durable rule:** A missing Discord application thread means there is no `EveCorporationApplication`. Ask for the character name. Do not treat it as a thread-create failure when pending rows all have threads.
**Skill update:** added the screenshare-application row.

## 2026-11-06 — Dread SRP refused: alt not in the strategic fleet

**Category:** pulse.technology
**Verdict:** needs-decision, then bug fix
**Discord:** explained the refusal and tagged the decision owner. They chose to accept the claim with a reviewer warning, then a fix + PR URL
**PR:** skill-only, then fix+skill
**Symptom vs cause:** A dread loss in a strategic fleet was refused with “Character not in fleet”. The opener's main was tracked in the fleet in a subcap. The dread alt never appeared in any ESI member poll. Polling was healthy through the fight, and other dreads in the same fleet were tracked and filed fine.
**Durable rule:** Check the victim character, not the account. Rule out a polling gap from `updated_at` around the kill time before calling it a tracker bug. When another character on the account was tracked, the claim is now accepted and flagged `not_tracked_in_fleet`.
**Skill update:** added the “Character not in fleet” row.

## 2026-11-03 — Planner bill ignores blueprint copy run cap

**Category:** pulse.technology
**Verdict:** bug
**Discord:** no reply (test-guild bot 403s the production help thread)
**PR:** fix+skill
**Symptom vs cause:** A large manufacturing run was priced as one job. A blueprint copy that only holds a few runs (a battleship copy at 10) is many jobs, and each job ceils materials and floors install cost on its own.
**Durable rule:** `max_runs_per_job` splits the plan. Blank stays one job. The pilot supplies the cap; eveuniverse has no max-runs column.
**Skill update:** added the planner BPC run-cap row.

## 2026-11-03 — SRP submit refused for a hull with no program

**Category:** pulse.technology
**Verdict:** clarify
**Discord:** no reply (test-guild bot 403s the production help thread)
**PR:** skill-only (same PR)
**Symptom vs cause:** Resolve succeeded for a character already on the account. The lost hull has no `ShipReimbursementProgram` row, so the wizard shows the ineligible-ship warning and does not offer a fleet.
**Durable rule:** Missing program row is `ship_is_no_eligible_for_srp`. Dump `user_id` first; a linked character can still be an uncovered hull.
**Skill update:** extended the SRP warning row.

## 2026-11-03 — Open technology threads (batch)

**Category:** pulse.technology
**Verdict:** mixed (clarify, note-to-self, needs-decision)
**Discord:** no reply (test-guild bot 403s production help threads)
**PR:** skill-only (same PR)
**Symptom vs cause:** Associates wiki `/en/` path and the old main-not-in-alliance banner are already explained by existing rows; Associate groups for market, subcapital production, and planetary interaction accept that affiliation. A fitting-paste request and a doctrine note on the decision owner's own ticket stay unimplemented. A two-word mining-killboard note is note-to-self.
**Durable rule:** Do not ping the decision owner on their own ticket. Do not add unnamed doctrine hulls from a one-line note. Do not mark a help ticket closed when the thread cannot be archived.
**Skill update:** Discord-reply note that a 403 does not close the row.

## 2026-11-03 — BUILD application tickets already fulfilled

**Category:** build
**Verdict:** clarify
**Discord:** no reply and not closed (test-guild bot 403s production threads)
**PR:** skill-only (same PR)
**Symptom vs cause:** Open `build` help tickets whose named corporation already has characters in BUILD, or whose named character is already in the requested corporation. One ticket is still `on_leave` and stays open.
**Durable rule:** Category `build` is a help thread, not the application forum. Processed means the join is already on the character or corporation row. Archive Discord before setting `HelpTicket.status`.
**Skill update:** added the BUILD-application row.

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
