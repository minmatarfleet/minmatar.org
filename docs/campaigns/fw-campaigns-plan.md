# Faction Warfare Campaigns — v1.2 Specification (implementation-ready)

Status: final pre-implementation revision, 2026-09-19. Supersedes every earlier draft in this file. Owner: TBD.
Companion page with mockups: https://claude.ai/artifact/Uxe9hGat5o7B5bokhmPFxG

---

## 1. Outcomes

**The pitch in one paragraph.** A campaign is a named, month-or-two operation over a few Faction Warfare systems. Alliance
members enlist, mostly by tapping "yes" when they join a campaign fleet. From then on the site counts every kill, loss,
complex, advantage site and fleet their characters take part in inside those systems, shows the war live (contest and
advantage per system with trends, who is out, what the enemy is doing right now), keeps a **standing fleet** up as the front
door, gives every pilot three small orders a day derived from an auto-proposed weekly plan, and turns the work into weekly
boards, awards and a retrospective that writes itself. Corporations, donors, the Thinkspeak content team and the Supply team
attach what they already do to it. It replaces the hand-typed campaign pages and feeds the monthly Warzone Report.

**What is different for the alliance when v1 ships.**

| Outcome | How we will know | Target |
| --- | --- | --- |
| More pilots undock between fleets | weekly active enlisted % (any scored action) | ≥ 60 % of enlisted by week three of the first campaign |
| There is always something to join | standing-fleet uptime in prime time (17:00–23:00 UTC); gangs per day formed by pilots without `fleets.create` | ≥ 80 % uptime by week two; ≥ 1 gang per day by week two |
| The invisible work becomes visible | site completions and advantage generated per pilot within one poll; Advantage board live | 100 % of `FacWar*` payouts from tracked characters attributed; ≥ 50 % of enlisted with a tracked character by week two |
| Nothing an enlisted pilot does in the systems is lost | stream coverage vs ESI ground truth; latency | ≥ 99.5 % of kills captured (measured baseline 99.5 %); ≤ 5 min typical, ≤ 15 min p90 |
| Leadership spends minutes, not hours | a campaign runs with name, systems and dates only | weekly plan auto-proposed, commander's order auto-drafted, weekly awards automatic |
| The community funds, supplies and tells the story | donation pool and its use; corp projects attributed; supply orders delivered; content attributed | pool covers weekly prizes; ≥ 1 funded corp project per campaign week; every campaign order delivered by its need-by date; ≥ 1 content item per week |
| The war is legible afterwards | monthly reports in the Warzone Report shape | generated from data with zero hand-typed numbers |

**The cut line.**

- **v1 launch = Calibration week + Phase 0 + Phase 1.** Enlist through three doors with the Campaign token inside the first
  enlist and per-character inclusion; kills and losses from the stream with two ESI safety nets; complexes, advantage sites,
  supply caches and battlefields from LP payouts with a calibrated event-code table; complex class inference; contested and
  operational-state snapshots; crowd-read advantage with our exact contribution; the Right now strip with the live hostile
  signal and the standing fleet; the weekly plan and today's orders; streaks; one-tap gangs; fits and SRP prefill; weekly
  boards; six weekly and three campaign awards; timeline with feed events; notifications with caps and quiet hours; the
  character readiness page; roster with timezone coverage; fleet tool attribution; zero-config manage page with KPI panel;
  the shared ESI gate; the Neocom entry.
- **v1 completes with Phase 1b during the first campaign:** the community layer (donations, corporation projects, content,
  supply).
- **Phase 2:** phases with interim reports and frozen weights, efficiency board, Rookie of the Week, more awards, gang impact
  cards, engagement-to-gang linkage, activity heatmap and heatmap-weighted orders, adaptive digest cadence and dormant handling,
  tracking-lapsed nags, beacon/outpost self-tag, close-out and retrospective generator, FC-programme prompt.
- **Not in this product:** hostile or neutral scoring, a general killboard, historical import, presence or location tracking,
  systems outside the Amarr–Minmatar warzone.

---

## 2. Decisions (final)

| Decision | Consequence |
| --- | --- |
| Live, data-driven campaigns over several FW systems replace hand-typed retrospectives | new `campaigns` app with durable per-campaign tables |
| Site completions come from ESI character notifications; complexes, RPs, beacons, outposts, supply caches and battlefields all pay LP through them | poll tracked characters; `TokenType.CAMPAIGN` = Basic + `read_notifications`; calibrated `FwPayoutEventCode` table with an admin tagging view |
| No backfilling; a campaign is scheduled before it starts and must not miss kills | ingest hook + 48 h sweep + per-character recent-killmails poll + LP-kill cross-check; lifecycle enforces "scheduled first" |
| Alliance members only; attribution starts when a character is included | outcomes kill / loss / awox / unscored; enlistment periods and per-character inclusion periods |
| This is a fleet alliance (production data); solo is the edge to grow, not the base | Join standing fleet is the single primary CTA; kill points scale with pilots on the mail; off-peak multiplier; contribution-mix bonus |
| A standing fleet that is always up beats looking-for-gang | `EveFleet(type=standing)` with rotating boss, ESI invites, boss watch; uptime is an outcome |
| Operators do not write objectives | per-system arcs; weekly plan auto-proposed from arc + momentum; orders derive from the week's gap |
| Complex class is recovered from the payout | jump-graph fixture, operational state, suppression term, `CampaignComplexCompletion`, tier-weighted points |
| Advantage must be visible though ESI has none | exact contribution from payouts; crowd readings with consensus and staleness; estimates labelled and never scored |
| Campaigns run one to two months | weekly boards default; participant-day aggregates; enlistment periods; monthly interim reports; phases in Phase 2 |
| The feed's events join the timeline | mirrored `CampaignEvent`s; live hostile-gang signal |
| ESI limits are per group × app × character plus the app-wide error limit | shared Redis gate, ETag, lapsed-token backoff, `eveonline` queue |
| Community layer attaches corporations, donors, Thinkspeak and Supply | ESI corporation projects on Director tokens; donations matched from the corp wallet journal by tag; `campaign` on posts, creator items and industry orders |
| Scopes are not in the alliance token and pilots have many characters | one readiness page: every character, In-campaign toggle, one-word state, one action per row, chained Update all |
| Zero-config campaigns, six weekly and three campaign awards, launch criteria | product review, 2026-09-19 (Appendix C) |

---

## 3. Who this is for (production data, 60 days to 2026-09-19)

451 users hold an alliance character; 292 had a kill or a tracked fleet in the last 60 days. Kill activity peaks at 19:00 UTC
(7,242 kill-actions in that hour over 30 days vs 156 at 08:00). Stated prime times: US 232, EU 150, AP 14, mixed 31.
The alliance fights in fleets: 312 of 388 users with kills got most of them alongside other members, 8 are mostly solo; top hulls
Typhoon, Thrasher Fleet Issue, Tempest Fleet Issue, Raven. 21 FCs ran 126 fleets; three ran 65 of them. 130 users joined in the
period; 97 have a kill, 106 a fleet. 115 users already hold a character with the notifications scope. Median loss-to-kill 0.10.
30.6 % of our kills were in Auga, Kourmonen and Kamela; Amamake alone was a third.

| Persona | Size | Today | What the campaign gives them | Enlistment door |
| --- | --- | --- | --- | --- |
| **Fleet Regular** | ~150 | 6+ fleets/60 d, battleship doctrines at 19:00, low losses | fleet-attended points, fleet-linked kills, standing fleet between ops, SRP in one tap, weekly Iron Wall | the fleet join prompt: "this fleet counts for Bleak Lands Push, enlist?" |
| **Hunter** | ~40 heavy, ~65 light | kills outside fleets, Thrashers and frigates, Amamake regulars | hostile gang detected, the standing fleet to fall back on, gang bonus, killfeed, rolling-7 and Your TZ boards | the strip's live hostile signal and the Discord gang ping |
| **Newcomer** | 130 in 60 d | arrives via new-player fleets; 75 % have a kill within 60 d | first-timer orders, fits with SRP tags, First Blood / First Plex | onboarding and the first new-player fleet; Advocates as sponsors |
| **FC** | 21 | 126 fleets; three people carry half | campaign on the fleet form, reports for AARs, Warlord, less admin | first; they create the campaign fleets |
| **Site runner** | small, unmeasured until the poll runs | plexes, RPs, beacons; invisible today | site credit within one poll, Advantage board, Pathfinder weekly, class-aware orders | the token upgrade is their enlistment; the 115 with the scope are day-one adopters |
| **Off-hours pilot** | AP 14 + mixed | alone in dead hours, holds systems nobody sees | off-peak multiplier, solo RP/plex orders, Your TZ board, coverage chart shows their hour | orders and digest at their prime time |
| **Industrialist / Supply** | Mining 69, PI 54, production 36, freighters 27, market 34 | rarely undock into FW | campaign orders on the Supply card, Supply board, Quartermaster mention, contribution-mix credit | attribute an order to the campaign |
| **Thinkspeak** | tribe group `pulse.thinkspeak` | posts, streams, videos | Content card, live-stream signal on the strip, Voice of the Front mention | attribute a post or stream |
| **Corporation leadership** | 207 corps, directors with wallet scope | fund and run corps | corp projects on the campaign page as the in-game reward engine; donation instructions | a director token with the projects scope |
| **Dormant** | 159 | no kill or fleet in 60 d | one weekly "what you missed" (Phase 2), phase starts | phase launches and a friend's gang ping |

**Adoption plan.** Enlist where people already are: the fleet prompt and the gang ping, with the web dialog as fallback. Token
upgrade inside the first enlist for the primary character; the rest on the readiness page. Launch with a commander's order and
the first weekly plan; the first Thursday awards post is the second launch. Brief the 21 FCs and the Thinkspeak and Supply
chiefs before launch. Measure weekly on the KPI panel.

---

## 4. Player experience

The page has one job: turn "I have forty minutes" into "I'm undocking, and probably with someone." Four questions, in
order, before any standings: Why now? What do I do? Who's out there? What do I get?

### 4.1 The first screen (hero, stat bar, Right now strip; refresh 60 s)

- **Hero**: identity (name, week n of m, campaign tag), one-line objective, countdown, commander's order. **One action block**:
  **Join standing fleet** as the single primary (an ESI fleet invite to the pilot's character, naming system, size and boss),
  **Form a gang** and **Undock solo** (scrolls to orders and fits) as secondaries, Leave and alert settings as small links.
  Counts (enlisted, out now, kills, losses, sites, advantage this week) live in a **stat bar beneath the hero**, never inside it.
- **Right now strip**: **active pilots** (enlisted characters on a campaign killmail or site payout in the last 30 minutes, plus
  members of open campaign fleet instances); **system heat** (kills in the last hour per system, all mails, unscored); **hostile
  gang detected** (the feed's live `fleet_active` events on the Amarr side for campaign systems, the strongest reason to undock,
  free because the feed already clusters engagements per side); the **standing fleet card**, always present (boss, size, system,
  voice, uptime today, handovers; **Take the standing fleet** when nobody is boss); **gangs forming**; **you** (streak, orders,
  rank change, last action, next timer); a **latest ticker**; a Thinkspeak member **streaming the campaign** when live.

### 4.2 The week's plan, and today's orders

**Operators do not write objectives.** A campaign has one **arc** per system, set once from the system goal and the campaign
dates ("capture Kamela by 27 Sep", "hold Kourmonen", "hold Auga"). Every Thursday at 11:00 the system proposes a **weekly plan**
from the arc and last week's momentum; the operator accepts or nudges the numbers in one click (auto-accepted after 24 h).

- **Capture systems** are measured in **victory points**, the only unit that flips a system. Weekly target = VP needed to stay on
  the arc's schedule (`remaining VP ÷ weeks left`), shown as plex-equivalents **at our current advantage** ("≈ 28 medium plexes").
  Progress from the VP delta in the snapshots; contributors from our tracked captures.
- **Defend systems** are a **ceiling**, not a count: enemy contest under a line and our advantage above one, scored as days
  under the line this week. Defensive plexing enters the plan only when enemy contest is above ~10 %; otherwise the plan asks for
  outposts, supply caches and kills in the system.
- **Momentum targets**: last week's gain × 1.2, floored at a reachable minimum, capped at 1.5 × the campaign's best week. If the
  arc slips, the card says so plainly ("at this pace Kamela flips 1 Oct, not 27 Sep") and raises the target gently.
- **Pace, not pass/fail**: every bar carries a pace marker; language is *on pace*, *behind*, *ahead*; nothing turns red before
  Thursday; the Thursday post celebrates the gain against last week even when the target was missed.
- **Today's orders derive from the plan**: the generator splits each system's remaining gap over the days left and the pilots
  active this week, scaled by each pilot's history (a five-plex-a-day pilot gets three, a newcomer one), so an order can say
  "closes 2 % of this week's gap". Capture systems generate plex and kill orders; defend systems advantage and kill orders;
  advantage below its line generates rendezvous, beacon and outpost orders. A one-line **commander's order** sits above,
  auto-drafted from the plan when nobody writes one. Completion is detected from attribution, never self-reported. Full-set
  bonus; weekly "active 5 of 7 days"; a first-timer pool for a pilot's first seven days. Fits are a link from the orders
  (role-labelled `CampaignFitting`, one-tap EFT, SRP tag), not a card of their own.
- **Campaign-level milestones** stay on the arc (flip, hold, kills, ISK, sites, gangs, enlisted, supply, projects) and are
  evaluated at close-out; nothing in between for the operator to maintain.

| Order kind | Example | Points |
| --- | --- | --- |
| `fleet_attend` · `fleet_kill` | Fly in a campaign fleet · Be on a campaign fleet kill | 15 · 20 |
| `standing_fleet` | Fly in the standing fleet for 30 minutes | 20 |
| `kill_any` · `kill_with_enlisted` | Get 1 kill in a campaign system · Be on a kill with 2+ enlisted pilots | 20 · 30 |
| `gang` | Form or join a gang | 30 |
| `plex_in_system` · `plex_class_in_system` | Capture 2 plexes in Kamela · Capture a Medium or larger plex in Kamela | 40 · 50 |
| `rendezvous_in_system` | Complete a Rendezvous Point in Kamela (a beacon or outpost also counts) | 40 |
| `supply_cache` | Kill a Supply Cache in a campaign system | 50 |
| `advantage_push` · `advantage_sweep` | Generate 6 % advantage in Kamela today · Report advantage for all campaign systems | 60 · 15 |
| `frigate` · `first_plex` (first-timer pool) | Undock in a frigate and get on any mail · Capture your first plex | 10 · 40 |
| `weekly_active` | Active 5 of 7 days | 100 |

**To calibrate:** VP per complex class at a given advantage is not published in a usable form; measured from our own tracked
captures against VP snapshots in the calibration week, kept editable.

### 4.3 Enlisting, and getting every character ready

Three doors: the **fleet join prompt** (one tap, no dialog), the **Discord gang ping** (enlist inline), the **web dialog**.
Kills and losses count for every included character immediately; site credit, advantage and the standing-fleet invite need the
Campaign token; corporation projects need a director token with the projects scope. None of those scopes are in the standard
alliance token and most pilots have several characters, so the token step is one clean page:

**Your characters for campaigns** (`/account/campaigns/`, embedded in the enlist dialog, linked from the hero's "3 of 6 tracked"):

- One row per character: **In campaign** toggle (all in by default; excluding and re-including opens a new inclusion period, so
  attribution follows the character from that moment), corporation, token today, what it counts for, one-word state
  (**Ready**, **Needs update**, **Lapsed**, **No token**); tabs by state, needs-update first.
- One action per row: *Update to Campaign*, *Update Director token* (adds the projects scope without dropping corporation
  scopes), *Re-authorise*: the existing add-character flow with `token_type` and `character_id`, redirecting back.
- **Update all** chains one SSO round trip per character, progress persisted in the session so a closed tab or a skipped login
  resumes; each completed login updates its row out of band.
- A plain explanation of what each token adds and the read-only promise: the only write is the fleet invite the pilot asked for.
- The Enlist button starts the chain for the primary character first, so most pilots finish enlisted *and* tracked in one round trip.

### 4.4 The standing fleet, and gangs

**The standing fleet is the campaign's front door.** One `EveFleet(type=standing, campaign)` meant to be up for the whole
campaign: free move, a fleet advert named after the campaign, the campaign voice channel. Any enlisted pilot may **take** it
when nobody is boss; the existing boss re-discovery in fleet tracking follows a rotating boss so the instance stays tracked
across handovers. **Join** sends an ESI fleet invite to the pilot's character through the current boss's token
(`POST /fleets/{id}/members`, scope in Basic, `fleet` bucket 1,800 per boss). Standing-fleet time earns fleet-attended points
once per campaign day plus minutes in fleet; kills while in it carry the fleet bonus. `standing_fleet_watch` records uptime and
handovers and pings enlisted pilots online in campaign voice when it needs a boss.

**Gangs** remain for ad-hoc groups that want a different ship class or system. **Form a gang**: ships, system (defaults to the
hottest), voice channel, computed ping audience, one line, Start; `EveFleet(type=gang, campaign)` via the quick-start path with
ESI tracking; the creator must be fleet boss in game ("waiting for fleet" state + hint DM otherwise); gated by
`campaigns.form_gang`, granted to every enlisted member. **Gang ping** to the campaign channel and as a DM to pilots active in
the last hour, one per pilot per two hours, **no DMs while a strategic campaign fleet is active**; a gang absorbed into a bigger
fleet closes when its instance empties. **Gang bonus**: kills with 2–10 enlisted pilots on the mail earn +5 each; the gang's FC
+2 per gang kill.

### 4.5 Taking the fear out of undocking

Role-labelled fits with one-tap EFT and SRP tags, linked from the orders. **Submit SRP** on any campaign loss in an eligible fit,
prefilled with killmail and linked gang or fleet. Losses cost −3 (−1 in a gang or fleet); a day never goes negative. **Visible
impact**: after a plex capture the system card shows "−0.4 % from your capture" for a few minutes.

### 4.6 Systems: status and trend

Every system card has the same three blocks so gaining or losing ground reads at a glance: **contest** (enemy %, Δ 24 h, 7-day
trend), **advantage** (both bars, net, Δ 24 h, 7-day trend of readings, age of the reading, Report), **kills and losses** in 24 h
with the change against the prior day and a split bar. A chip in the corner derives from the trends: gaining ground, holding,
losing ground. Cards are ordered most contested first.

### 4.7 Boards, streaks and awards over a long campaign

- **Weekly boards are the default** (campaign week Thursday 11:00 → Thursday 11:00); scopes *This week*, *Overall*, *Rolling 7*;
  by *all*, *Your TZ* (`EvePlayer.prime_time`), *tribe*; metrics points, kills, ISK, sites, advantage, fleets, supply. My row pinned.
- **Streaks that survive real life**: daily with one shield per week for the first 14 days; from day 15 the streak counts active
  weeks (3+ active days) with a personal-best marker.
- **Awards, v1**: six weekly (Top Gun, Plex Marathon, Pathfinder, Gang of the Week, Iron Wall, Saboteur) announced Thursdays with
  Voice of the Front and Quartermaster mentions; three campaign (Warlord, Closer, Ever Present) at close-out. First Blood and
  First Plex are quiet one-time DMs.
- **Interim reports** at each calendar month end in the Warzone Report shape.

### 4.8 Advantage

Advantage multiplies the victory points of every capture; both sides hold 0–100 %, net is ours minus theirs. **ESI exposes
none of it** (§5.3). **Exact: our contribution** from tracked payouts (RP +2 %, Propaganda Beacon +2 %, Listening Outpost −2 %
enemy, Supply Cache −2 % enemy, Battlefield ≈ +15 %) drives the Advantage board and hero stat. **Crowd-read: the absolute
value** via one-tap **Report advantage** on every system card; consensus (median of readings in the last hour when ≥ 2, else the
latest), age and reporter; stale after 3 h, hidden after 12 h; an **estimate** between readings (last consensus + our tracked
completions), labelled, never scored; +5 per system per pilot per two hours, +15 for a sweep; readings > 15 points from consensus
held; three held readings in a week mutes the reporter. Advantage lines in the weekly plan evaluate met / unmet / unknown from
readings ≤ 3 h old.

### 4.9 Roster and timezone coverage

`/campaigns/[slug]/roster/`: **coverage by hour** (enlisted pilots with a scored action per UTC hour over 7 days against hostile
fleet-activity events per hour, so the hole where the enemy plays and we do not is obvious; counts by stated prime time; out now
by prime time) and the **roster**: one row per pilot with primary character, corporation, stated prime time, observed play hours
(histogram from participant-day activity, which corrects a stale prime time), last action, streak, characters tracked ÷ included,
this week's points; tabs by prime time, out now, directors. Coverage feeds the off-peak multiplier and the commander's order draft.

### 4.10 Notifications that pull, not spam

Pull types (gang forming, standing fleet needs a boss, activity nearby, streak at risk) are opt-in per type, capped at three
per pilot per day, prime-time quiet hours; everything else is event-driven or a daily digest at the pilot's chosen hour (§9).

### 4.11 The community layer (Phase 1b)

- **Corporation projects (ESI, new).** CCP's projects are the in-game reward engine: a corp reserves ISK, sets a goal
  (`capture_fw_complex`, `defend_fw_complex`, `destroy_ship`, `lost_ship`, `earn_loyalty_point`, `deliver_item`, `manufacture_item`,
  `manual`…) with filters for locations, factions, ships and items; ESI exposes name, description, progress, reward, state and a
  paginated per-character contributor list (scope `esi-corporations.read_projects.v1`, group `corp-project`, 600 tokens per 15 min
  per director). Add the scope to Director tokens and one scope list to `update_corporation`; poll each allied corp every 30
  minutes; attribute by campaign tag in name or description, or automatically when an FW-complex or ship project's `locations`
  intersect the campaign systems while active (manager override both ways). Card: corp, kind, progress, ISK remaining, top
  contributors; enlisted contributors get "ISK earned from campaign projects". No extra points: the project's ISK is the reward.
- **ISK donations (automated).** Every allied corp's wallet journal is already synced hourly with `ref_type`, `first_party_id`,
  `amount`, `date`, `description` and `reason`. A campaign declares `donation_corporation`, `donation_division` and `donation_tag`
  (default its short code, e.g. `BLP`). `player_donation` entries whose `reason` contains the tag become `CampaignDonation` within
  the hour; `anon` in the reason hides the name. Card: pool (donated − allocated to attributed project rewards − prizes paid),
  donor count, recent and top donors. Donors get a **Patron** mark, never points. Manage page prints the instruction and records
  prize payouts.
- **Thinkspeak content.** `campaign` on `EvePost`; `CampaignContent` for creator items (post, video, VOD, stream, reddit post),
  set by `pulse.thinkspeak` members (`campaigns.attribute_content`); tag-matching items suggested. Content card; a member live on
  Twitch with the tag shows on the strip. Weekly **Voice of the Front** mention.
- **Supply orders.** `campaign` on `IndustryOrder` (`campaigns.attribute_orders`). Supply card: open campaign orders with need-by
  dates and delivery progress from assignments. **Supply board** metric (ISK value delivered on campaign orders), weekly
  **Quartermaster** mention; supply counts as one of the "three ways" for the contribution-mix bonus.

---

## 5. What the research established

### 5.1 Kills: the stream is 99.5 % complete and a few minutes late

BearThatCares's 203 `FacWarLPPayoutKill` notifications (24 Aug → 13 Sep) carry killmail ids, an independent ground truth.

| Source | Coverage | Notes |
| --- | --- | --- |
| Production feed (`FeedKillmail`) | **202 / 203** | the miss, killmail 138423945 (Amamake, 13 Sep 19:19), is not on zKillboard at all |
| Dev feed | 113 / 203 | 100 % on days the dev poller ran; 0 % when down |
| `EveCharacterKillmail` (4-hourly refresh, first page) | 1 / 203 | not a usable net as scheduled today |
| Production ingest lag (last 2,000 mails) | median 153 s · p90 471 s · p99 21 h | p99 is the catch-up cursor; the 48 h sweep absorbs it |

Feed constraints: 30-day purge, no ISK column, no attacker index. Campaigns keep durable copies.

**Reconciliation.** The stream is the fast path, never the only path. `GET /characters/{id}/killmails/recent/` (scope in Basic,
covers **every included character**) returns id **and hash** for kills and losses; observed depth ≈ last 100 mails, `Expires`
5 min, so a 30-minute poll makes depth irrelevant. Kill payouts of tracked characters confirm coverage. Each campaign mail
records `sources` and `first_seen_via`; the KPI panel shows stream coverage, latency percentiles and mails absent from
zKillboard, alerting below 98 % or above a 15-minute p90.

### 5.2 Sites: LP payout notifications and the event codes

The militia corporation (`1000182`) sends a character notification for every LP payout. Live pull 2026-09-18 (500 rows,
22 Aug → 18 Sep): 54 `FacWarLPPayoutEvent`, 202 `FacWarLPPayoutKill`, 1 `FacWarLPDisqualifiedKill`.

| `event` | Seen | `amount` | `charRefID` / `itemRefID` | Systems | Reading |
| --- | --- | --- | --- | --- | --- |
| 371 | 3 | 31 / 248 / 265 | set / set (site id) | Dal | **Complex capture**; amount = base × system × contested × suppression ÷ pilots inside |
| 516 | 50 | 10,000 flat, one 15,000 | null / null | Kamela 34, Sosala 14, Hadozeko 2 | **Advantage site, probably Rendezvous Points**. RP, beacon and outpost all pay 10,000; the in-game text is rendered from the code, so beacons and outposts may carry codes not yet seen. 15,000 = Supply Cache |
| 359 | 1 | 52,500 | null / 14030 | Sosala, 27 Aug 01:02 | **Unconfirmed large payout**. Battlefields pay variable amounts, sometimes > 100k (Kaleb); this character shows exactly one payout ≥ 20,000 in the window |
| 367 | 202 | 12–503 | victim / **killmail id** | various | Kill payout; doubles as a missed-kill check |

**LP reference.** Complex: base by class × system (×1.5 frontline, ×1.0 command, ×0.01 rearguard) × contested factor (1.0 in
enemy-held; else enemy contested %) × suppression (insurgency stages 2–5: ×1.05 / 1.10 / 1.15 / 1.20), split between pilots
inside. Base tiers: 10,000 Scout NVY-1 · 12,500 Scout NVY-5 · 15,000 Small NVY-1 · 17,500 Small ADV-1 · 18,750 Small NVY-5 ·
20,000 Small ADV-5 / Medium NVY-1 · 25,000 Medium NVY-5 / Medium ADV-1 / Large NVY-1 / Large ADV-1 · 30,000 Medium ADV-5 /
Large NVY-5 / Large ADV-5 / Open · 45,000 FRF ELT-5 (frontline only). Rendezvous Point 10,000 (+2 %); Propaganda Beacon 10,000
(+2 %); Listening Outpost 10,000 (−2 % enemy); Supply Cache 15,000 (−2 % enemy, every damaging pilot); Battlefield variable
(≈ +15 %, 2,000 VP, winners).

**Calibration, not guesswork.** `FwPayoutEventCode` seeded with the three observed codes marked *unconfirmed*; every payout with
an unmapped or unconfirmed code lands in an **Unmapped payouts** admin view where Kaleb tags what the pilot did. Unknown or
unconfirmed codes never score. Probes: deploy a beacon or outpost on a tracked character (or read the in-game wording of the
11 Sep 14:34 Hadozeko payout); name one battlefield Kaleb ran (character, date, system) and match it.

**Complex class from the payout.** Group event-371 payouts by `(itemRefID, minute)` → one `CampaignComplexCompletion`
(`split_count` = payouts in the group, a lower bound). Operational state from a warzone jump-graph fixture (946 edges, exported
once from the SDE `mapSolarSystemJumps`) plus ownership, recomputed every 30 min and stored on snapshots (ESI's `/fw/systems/`
has no such field). Contested factor from the nearest snapshot. Suppression from a manager-set `CampaignSystemInsurgency` stage
(ESI has no insurgency endpoint) or proposed when residuals sit a consistent 5–20 % above a tier.
`base_est = amount × split ÷ (multiplier × contested × suppression)`, try `split … split + 3`, tier within ±4 %; write tier, class
or collision set, suppression used, confidence (high only when the tier is unique, contested ≥ 5 % and the stage was recorded).
Points follow the base tier, never a guessed name; only high-confidence rows feed class-specific orders. Sanity check: the three
Dal captures resolve to Small plexes at ~1.6–1.8 % enemy contest; unverifiable today because snapshots retain 8 days.

### 5.3 Systems and advantage

`/fw/systems/` returns only `contested`, `occupier_faction_id`, `owner_faction_id`, `victory_points`, `victory_points_threshold`
under every compatibility date (checked 2026-09-19; `Expires` 30 min). No operational state, **no advantage** (esi-issues #1335
open since Nov 2022; no third party publishes it). Today's poll stores a derived percent for 8 days and discards VP; we persist
VP and threshold, copy campaign systems to a durable table, and poll every 30 minutes.

### 5.4 ESI budget

**Rules** (live since Oct–Dec 2025; verified against live headers 2026-09-19). Error limit: 100 non-2xx/3xx per minute
application-wide → 420 everywhere until reset. Group buckets: per `group × application × character` (or `× IP` for public
routes), 15-minute floating window; 2xx = 2 tokens, 3xx = 1, 4xx = 5, 5xx = 0; over budget → 429 + `Retry-After`.

| Route | Group · bucket | Full fetches / 15 min / character | Our poll | Share |
| --- | --- | --- | --- | --- |
| `/characters/{id}/notifications` | char-notification · 15 | 7 | every 20 min, ETag | 20 % |
| `/characters/{id}/killmails/recent` | char-killmail · 30 | 15 | every 30 min, ETag | 3 % |
| `/killmails/{id}/{hash}` | killmail · 3,600 | 1,800 | on demand | negligible |
| `/fw/systems` (public, per IP) | factional-warfare · 150 | 75 | every 30 min | 1 % |
| `/fleets/{id}/members` (boss token) | fleet · 1,800 | 900 | every 30 s per open fleet (existing) + invites | 10 % |
| `/corporations/{id}/projects…` (director token) | corp-project · 600 | 300 | every 30 min per corp + details | small |
| `/characters/affiliation`, `/universe/names` | none | error limit only | existing | — |

**Existing spend** (inventory of `app/settings_celery.py`): three workers, one per queue (`celery`, `eveonline`, `market`);
everything without an explicit queue (Discord, the 7-second zKill stream, notification delivery) shares `celery`. The 4-hourly
character sweep ≈ 12k calls over 778 alliance characters with tokens; structure notifications poll 260 characters in minute
buckets (~26/min) and are the only place that honours 429; `update_fleet_instances` runs every 30 s per open fleet with no
limiter; corporations refresh hourly with 7 wallet divisions. No shared limiter; `X-Esi-Error-Limit-*` never read; ETag disabled
globally (`use_etag=False`); ~25 raw `requests` call sites bypass django-esi's buckets, cache and retries.

**Campaign spend at full enlistment** (436 users, 778 characters): ≈ 65 calls/min, the size of one character sweep, spread
evenly. Risks: revoked tokens (5 bucket tokens + 1 error-limit unit each; 100 in a minute would 420 the platform), `celery`
contention, the unlimited fleet poll.

**The gate (Phase 0 prerequisite).** Shared Redis gate: store remaining per `(group, character)` and the app-wide error budget
from every response; skip and reschedule under a 20 % reserve or error budget < 20; on 429 write `paused_until = now +
Retry-After`. ETag on campaign polls (304 = 1 token). Never poll a bad token: skip `esi_suspended`; on first 4xx set
`tracking_lapsed_until` with backoff 1 h → 4 h → 24 h. Minute-bucket with jitter, `QueueOnce`, run on `eveonline`. Priority under
pressure: fleet tracking and invites → site payouts → recent killmails → snapshots → corp projects → cross-checks. KPIs: 429s/hour,
min error-limit-remain/hour, per-group remaining, lapsed tokens; alert at error-limit-remain < 30 or any fleet-group 429.
Platform hygiene (recommended, not blocking): limiter + `QueueOnce` on `update_fleet_instances`; global ETag with
`HTTPNotModified` handling; raw call sites through the gate.

### 5.5 Everything else we reuse

| Need | Existing | We add |
| --- | --- | --- |
| Quick-start fleets, fleet tracking | `POST /fleets/start-now`; `EveFleetInstance` members every 30 s; boss re-discovery | types `standing` and `gang`, campaign preset, `campaigns.form_gang`, ESI invites, fleet ↔ killmail linkage |
| Feed events | `FeedEvent` `fleet_active` (per system, per side, pilot count, `is_active`), `killmail_batch`, `contested_change`; not purged | campaign mirror, live hostile signal |
| Notifications poller | `structures.tasks` minute buckets, rate limit, downtime deferral, 429 handling | generic `FacWar*` parser and store |
| Token upgrade | `/api/eveonline/characters/add?token_type=&character_id=&redirect_url=` | `TokenType.CAMPAIGN`; `scope_group()` returns Campaign without corp membership; readiness page and chain |
| Corp wallet journal | `EveCorporationWalletJournalEntry` hourly, all divisions, `reason` stored | donation matcher |
| Corp scopes | `get_director_with_scope`, five scope lists in `update_corporation` | `read_projects` list, `EveCorporationProject` |
| Posts, creators, orders | `EvePost` tags + tribe groups; `CreatorItem` with live status; `IndustryOrder` tribe groups + notification audience | `campaign` FKs, `CampaignContent` |
| SRP, fittings | reimbursements linked to fleets; doctrines with EFT | prefill from a campaign loss; role tags |
| Site notifications | registry, `notify_users`, web push / Discord DM / EVE mail | campaign types, `DiscordChannel.receive_campaign_pings`, per-user caps and quiet hours |
| Permissions | `FEATURE_DEFINITIONS`, `check_feature` | `campaigns.*` keys |
| Boards | survey-style materialised aggregates | `CampaignParticipantDay` |
| Frontend | `Progress`, `SystemCard`, `Countdown`, `CountUpAnimation`, `Table`, reels, htmx partials + `ErrorRefetch`, warzone `types.ts`; Neocom EvE icons are CCP PNG glyphs via `<img>` wrappers | campaign pages and partials; `CampaignsEvEIcon` wrapping the existing `64px-Sovereignty.png` (in the repo) |

Why not add the notifications scope to Basic: `token_satisfies_type(BASIC)` would fail for every existing Basic token until
re-auth and break tribe and fleet gates. Naming: `surveys.SurveyCampaign` exists; the app is `campaigns`, model `Campaign`.

---

## 6. Architecture

### 6.1 Data model (`backend/campaigns`, plus models in `eveonline` marked so)

```
Campaign                  slug, short_code (donation tag), name, tagline, description_md, cover_image_url
                          status draft | scheduled | active | completed | archived; start_at, end_at (nullable); visibility
                          created_by, discord_channel_id, voice_channel_ids, default_fleet_audience
                          scoring JSON, order_pool JSON (defaults); commander_order_text, commander_order_set_at
                          donation_corporation → EveCorporation, donation_division
CampaignSystem            campaign, solar_system_id, name, region_id, role (primary|secondary|staging), goal (capture|defend|contest|none)
                          added_at, retired_at; unique (campaign, system); on save assert FeedMonitoredSystem exists
CampaignSystemArc         campaign_system, target_state (flip|hold), due_at, contest_ceiling, advantage_floor, vp_needed_at_start
CampaignWeekTarget        campaign_system, week_start, metric (vp_gain|contest_ceiling), target, proposed, accepted_by, accepted_at,
                          progress, pace_expected, days_under_line, last_week_actual, projected_arc_date
CampaignSystemInsurgency  campaign_system, suppression_stage, corruption_stage, valid_from, valid_until, source (manager|inferred), confirmed
CampaignFitting           campaign, fitting → EveFitting, role_label, srp_eligible, order
CampaignEnlistment        campaign, user, status (active|left|removed), source (fleet_prompt|gang_ping|web|admin)
                          notify_fleets, notify_gangs, notify_standing_fleet, notify_activity, notify_thresholds, notify_streak, notify_digest, digest_hour
CampaignEnlistmentPeriod  enlistment, enlisted_at, left_at
CampaignEnlistmentCharacter
                          enlistment, character → EveCharacter, included_from, included_until (nullable)
                          all of the user's characters are included at enlistment; new characters join included;
                          a killmail or payout counts only if its character was included at that moment
CampaignStandingFleet     campaign, fleet → EveFleet (type=standing), current_boss_character_id, taken_at, handovers,
                          uptime_minutes_today, advert_name, voice_channel_id
CampaignDailyOrder        campaign, day, kind, params, points, scope (all|user), user, gap_share_pct
CampaignOrderProgress     order, user, progress, completed_at
CampaignSystemSnapshot    campaign_system, captured_at, victory_points, victory_points_threshold, contested_percent,
                          occupier_faction_id, owner_faction_id, contested_state, operational_state (frontline|command|rearguard)
CampaignAdvantageReading  campaign_system, reported_by, reported_at, our_pct, enemy_pct, source (card|sweep|manager), status (accepted|held|rejected)
CampaignAdvantageState    campaign_system, as_of, our_pct, enemy_pct, basis (consensus|single|estimated|unknown), reading_age_minutes,
                          our_generated_since_reading, enemy_removed_since_reading
CampaignKillmail          campaign, killmail_id, killmail_hash, killmail_time, solar_system_id, victim character/corp/alliance/ship_type,
                          isk_value, is_pod, is_solo, attacker_count, enlisted_attacker_count, outcome (kill|loss|awox|unscored),
                          fleet (nullable), sources {stream, recent_killmails, lp_payout: seen_at}, first_seen_via, on_zkillboard
                          unique (campaign, killmail_id); index (campaign, killmail_time), (campaign, outcome)
CampaignKillmailParticipant
                          killmail, character_id, user (nullable), enlisted, role (attacker|victim), ship_type_id, damage_done, final_blow
                          stored only for mails with ≥ 1 enlisted participant; unscored mails keep counts only
EveCharacterFwLpPayout    [eveonline] character, notification_id (unique), notification_type, occurred_at, amount_lp, corp_id, event_code,
                          location_id, ref_id, char_ref_id, disqualification_type
FwPayoutEventCode         [eveonline] event_code (unique), site_kind, label, amount_rule, confirmed, confirmed_by, confirmed_at, valid_from
CampaignSiteCompletion    campaign, payout (unique), user, campaign_system, occurred_at, amount_lp, event_code,
                          site_kind (complex|advantage_site|supply_cache|battlefield|unknown), complex (nullable)
CampaignComplexCompletion campaign, campaign_system, site_ref (itemRefID), completed_at, split_count, operational_state, contested_factor,
                          suppression_used, base_lp_tier, inferred_plex_class, class_candidates, confidence; unique (campaign, site_ref)
CampaignParticipantDay    campaign, user, day (11:00 UTC boundary); kills, losses, isk_destroyed, isk_lost, final_blows, solo_kills, gang_kills,
                          plex_captures, plex_by_class, advantage_sites, supply_caches, battlefields, site_lp, advantage_generated_pct,
                          enemy_advantage_removed_pct, advantage_readings, fleets_attended, fleets_led, gangs_led, standing_fleet_minutes,
                          minutes_in_fleet, orders_completed, project_isk_earned, supply_isk_delivered, points, active
                          unique (campaign, user, day)   ← the only table boards read
CampaignParticipantStat   campaign, user; roll-up + current_streak, streak_mode, best_streak, shield_used_week, rank, tz_rank, tribe_rank,
                          last_active_at, tracked_characters, included_characters, tracking_lapsed_characters,
                          active_hours_utc JSON (24 buckets, last 7 days), observed_prime_time
CampaignEvent             campaign, kind, occurred_at, ended_at, payload, system, user, side (ours|hostile|neutral|none),
                          source (campaign|feed), feed_event (nullable, unique), fleet (nullable)
CampaignAward             campaign, user, code, label, awarded_at, payload, scope (campaign|week), week_start

-- community layer (Phase 1b) --
EveCorporationProject     [eveonline] corporation, project_id (unique), name, description, kind, config JSON, state, career,
                          progress_current, progress_desired, reward_initial, reward_remaining, created, expires, finished, last_modified
EveCorporationProjectContributor
                          project, character_id, name, contributed, synced_at; unique (project, character_id)
CampaignCorporationProject
                          campaign, project (unique), attribution (tag|auto_locations|manual), attributed_by, attributed_at
CampaignDonation          campaign, journal_entry → EveCorporationWalletJournalEntry (unique), donor_character_id, user (nullable),
                          amount, reason, donated_at, anonymous, excluded, excluded_reason
CampaignPrizePayout       campaign, amount, paid_to_user, paid_at, journal_entry (nullable), note
EvePost (+)               campaign → Campaign (nullable)
CampaignContent           campaign, kind (post|video|vod|stream|reddit_post), post (nullable), creator_item (nullable),
                          attributed_by, attributed_at, suggested
IndustryOrder (+)         campaign → Campaign (nullable)

-- Phase 2 --
CampaignPhase             campaign, index, name, start_at, end_at, objectives, scoring overrides, primary_system_ids, closed_at, report_json
```

Changes to existing models: `EveFleet.campaign` (nullable FK) and fleet types `standing`, `gang`; `FeedSystemContestedSnapshot`
gains `victory_points`, `victory_points_threshold`, `contested_state`, `operational_state`; `DiscordChannel.receive_campaign_pings`;
`TokenType.CAMPAIGN`; `DIRECTOR_SCOPES` += `esi-corporations.read_projects.v1`.

### 6.2 Correctness over two months

| Changes over time | Handling |
| --- | --- |
| Pilots leave and rejoin; characters toggled in and out | enlistment periods and per-character inclusion periods; attribution tests "character included at that moment" |
| Characters added, moved between users, dropped | mapping resolved at attribution and re-resolved by the 48 h sweep; nightly re-resolution of the last 14 days when any `EveCharacter.user` changed |
| Tokens expire or get suspended | `tracking_lapsed_characters`; lapsed backoff in the gate; readiness page shows Lapsed; tracked % over time on the KPI panel |
| Systems flip, targets move | arcs per system; systems retire from a date; operational state recomputes every 30 min |
| Insurgencies (2 weeks each) | `CampaignSystemInsurgency` date ranges |
| CCP changes LP tables or codes | `FwPayoutEventCode` and base tiers carry `valid_from`; new codes surface within one poll |
| Weights need tuning | recomputed retroactively in v1; frozen closed phases in Phase 2 |
| Standing fleet boss logs off | boss re-discovery; "needs a boss" state and ping; handovers recorded |
| Storage | ~18k mails, ~27k participants, ~9k snapshots, ~12k participant-days for 200 pilots over 60 days (production: 9,115 mails/30 d across Auga, Kourmonen, Kamela; ~4 participants/mail). Archive to JSON on `archived` |

### 6.3 Pipelines (Celery, new `CELERYBEAT_CAMPAIGNS` list; ESI polls on the `eveonline` queue through the gate)

| Task | Schedule | What it does |
| --- | --- | --- |
| `attribute_killmail` | on feed ingest commit | for scheduled/active campaigns covering the system (cached 60 s): write mail + participants, map characters → users, flag included, derive outcome, bump live counters, order progress, streak day |
| `sweep_recent_killmails` | every 10 min | re-attribute the last 48 h of feed mails in campaign systems; re-resolve participants |
| `poll_enlisted_recent_killmails` | every 30 min, active campaigns | every included character (Basic scope), ETag; fetch missing mails by id+hash; set `first_seen_via`, `on_zkillboard` |
| `poll_campaign_lp_payouts` | every 20 min (10 with ETag) | tracked characters, minute-bucketed; store every `FacWar*` row once; attribute site completions by system, window, inclusion; cross-check kill payout ids |
| `infer_complex_classes` | after each payout poll | group by site id + minute; resolve tier and class; propose suppression stage; queue unmapped codes |
| `poll_fw_contested_snapshots` (extended) | every 30 min | persist VP; operational state for every monitored system from the jump graph + ownership; copy campaign systems; threshold (25/50/75/90/100) and flip events; "from your capture" hints |
| `update_advantage_state` | every 10 min + on reading | consensus, outlier holds, estimate, staleness, events |
| `mirror_feed_events` | on rollup write + every 10 min | copy feed events for campaign systems into `CampaignEvent(source=feed)`, update live ones, side from accent |
| `campaign_lifecycle` | every minute | scheduled → active at start; active → completed at end; refuse active without prior scheduled coverage |
| `propose_week_targets` | Thursdays 11:00 | per system: target from arc schedule and momentum (last week × 1.2, floored, capped at 1.5 × best week); projected arc date; one-click acceptance, auto-accept after 24 h |
| `generate_daily_orders` | 11:05 UTC | commander's line (auto-draft from the plan if empty) + three personal orders per pilot from the week's remaining gap ÷ days left ÷ active pilots, scaled by history |
| `standing_fleet_watch` | every minute | boss present? size, system, uptime; on boss loss mark "needs a boss" and ping enlisted pilots online in campaign voice; record handovers |
| `link_fleet_killmails` | every 10 min + on fleet close | attach mails to fleet instances by window and tracked members; attendance minutes |
| `materialise_campaign_stats` | every 10 min | recompute today's and yesterday's participant-day rows only; roll up; rank every board scope from sums; streak rules; awards |
| `close_campaign_week` | Thursdays 11:05 | freeze rows, weekly awards and mentions, channel summary |
| `poll_corporation_projects` (1b) | every 30 min | per allied corp with a director holding `read_projects`: list active projects (cursor), upsert; for attributed or tag-matching projects fetch detail and contributors; auto-attribute by tag or by FW-complex/ship configs intersecting campaign systems; events |
| `match_campaign_donations` (1b) | hourly, after the corp wallet sync | `player_donation` to the campaign's corp and division with the tag in `reason` → `CampaignDonation`; recompute the pool |
| `suggest_campaign_content` (1b) | hourly | tag-matching creator items and posts → suggested `CampaignContent`; live streams with the tag feed the strip |
| `send_campaign_digests` · `close_campaign` | hourly · on completed | per-pilot digest at their hour; final stats, awards, monthly/retrospective JSON |
| feed and ESI health | every 5 min | stream paused > 10 min during an active campaign, coverage < 98 %, p90 > 15 min, error-limit-remain < 30, any fleet-group 429 → tech channel + Sentry; killfeed shows "feed delayed" |

Never missing a kill, without backfill: scheduled before start so the hook is live; the 48 h sweep, the recent-killmails poll
and the LP-kill cross-check each independently recover anything missed, including mails that never reach zKillboard.

### 6.4 Timeline: ours plus the feed's

Feed `fleet_active`, `killmail_batch` and `contested_change` events for campaign systems are mirrored into
`CampaignEvent(source=feed)` keyed by feed event, so a live engagement updates its row; side from the accent. Live hostile
events feed the strip and the activity-nearby nudge. Detected events are labelled "detected" and never score; clusters need
≥ 6 pilots and ≥ 5 kills in 20 minutes, so small gangs go unseen. Phase 2 links our detected engagements to the gang or fleet
that fought them and builds the hour × weekday heatmap.

---

## 7. Scoring and recognition

Weights live on the campaign with defaults; recomputed, never incremented. Only included characters of enlisted pilots score,
from inclusion. Pods listed but never scored; NPC-only mails dropped at ingest; awox gives no kill credit; a day never goes
negative; deduplicated by killmail id and notification id.

| Action | Points | Modifiers |
| --- | --- | --- |
| Kill | +10 × min(1, 5 ÷ enlisted on mail) | final blow +5, solo +10, in a tracked campaign fleet or the standing fleet +5 flat; ISK-destroyed points split the same way |
| Gang kill | +5 each | 2–10 enlisted on the mail; gang FC +2 per gang kill |
| Loss | −3 | −1 in a gang or fleet |
| ISK destroyed | +1 per 10M | split by enlisted on mail, capped per kill |
| Complex capture (371) | +15 + base tier ÷ 1,000 | Scout 25–27, Small 30–33, 20k tier 35, 25k tier 40, 30k tier 45, Elite 60; +10 in a primary system; unknown tier scores as Scout |
| Advantage site (516, 10,000) | +40 | RP, beacon or outpost; +10 in a primary system |
| Supply cache (516, 15,000) | +50 | every damaging tracked pilot |
| Battlefield (code TBC) | +60 | per tracked participant; scores only once the code is confirmed |
| Site soft cap | full → half | first eight sites per user per day in full, half after (multiboxers) |
| Advantage reading | +5 | per system per pilot per 2 h; sweep +15; held readings earn nothing |
| Order completed | as listed | full set +50; weekly +100 |
| Fleet attended · standing fleet day · fleet led · gang led | +15 · +15 · +40 · +20 | +30 attended if the fleet reached the primary system; standing fleet once per campaign day |
| Active day | +5 | streak +5/day from day 3, cap 25, one shield per week |
| Off-peak multiplier | ×1.25 | all points 03:00–14:00 UTC |
| Contribution mix | +20 % on the week | three different ways scored in the week (kills, sites, advantage, fleets, orders, supply) |

**Pre-launch simulation.** Run the default weights over the last 30 days of production mails and fleets and publish the top
twenty by persona; tune until site runners and gang hunters appear in it. Part of the calibration week.

---

## 8. API and permissions (`/api/campaigns`, Django Ninja, one endpoint per file)

| Method | Path | Feature | Notes |
| --- | --- | --- | --- |
| GET | `/campaigns` · `/campaigns/{slug}` | view (public: none) | list; detail with systems + snapshots + advantage state, arcs, week targets, counts, my enlistment + coverage |
| GET | `/campaigns/{slug}/now` · `/orders` · `/week` | view · enlisted · view | strip data (cached 60 s); today's orders with progress; this week's plan |
| POST/DELETE | `/campaigns/{slug}/enlist` | enlist | prefs; `source`; response lists untracked characters and the token-chain URL |
| PUT/DELETE | `/campaigns/{slug}/characters/{character_id}` | enlisted | include or exclude one of my characters |
| GET | `/campaigns/readiness` | enlisted | every character with token type, counts-for, state; chain state |
| POST | `/campaigns/{slug}/standing-fleet/join` · `/take` | enlisted | ESI invite via the boss's token; take the fleet when nobody is boss |
| POST | `/campaigns/{slug}/gangs` | form_gang | one-tap gang |
| POST | `/campaigns/{slug}/systems/{id}/advantage` · `/advantage/sweep` | enlisted | readings |
| GET | `/roster` (+ coverage by hour, by prime time) · `/leaderboard?by=&scope=&period=` · `/killmails` · `/sites?kind=` · `/systems/{id}/history` · `/systems/{id}/advantage` · `/timeline` · `/fleets` | view | boards from participant-days; killmails exclude `unscored` by default |
| POST · PATCH | `/campaigns` · `/campaigns/{slug}` | create · manage or creator | draft; edit, schedule, complete, commander's order |
| PATCH | `/campaigns/{slug}/week/{system_id}` | manage | accept or nudge the proposed target |
| PUT/DELETE/PATCH | `/campaigns/{slug}/systems/{id}` · `/fittings/{id}` · `/insurgency` | manage | remove systems only before start; retire from a date; fits; insurgency stage |
| GET | `/campaigns/{slug}/community` (1b) | view | donations pool and list, projects, content, supply |
| POST/DELETE/PATCH | `/campaigns/{slug}/projects/{project_id}` · `/donations/{id}` · `/prizes` (1b) | manage or corp director | attribute/detach a project; exclude a donation; record a prize |
| POST/DELETE | `/campaigns/{slug}/content` (1b) | attribute_content | attach a post or creator item; confirm a suggestion |
| PATCH | `/industry/orders/{id}` · `/posts/{id}` (1b) | existing | `campaign_id` |
| POST/PATCH | `/fleets` · `/fleets/{id}` | existing | `campaign_id` on create and edit; joining a campaign fleet returns the enlist prompt |
| GET | `/eveonline/characters/add?token_type=Campaign&character_id=…&redirect_url=…` | existing | token upgrade; `redirect_url` carries `next=` to chain |

Features: `campaigns.view`, `campaigns.enlist`, `campaigns.form_gang` (affiliation: alliance and associates); `campaigns.create`
(auth group, e.g. FCs); `campaigns.manage` (staff; creator in code); `campaigns.attribute_content` (`pulse.thinkspeak`);
`campaigns.attribute_orders` (`supply.*` chiefs + `industry.order.submit`). Corp project attribution: `campaigns.manage` or a
director of the owning corporation. Run `sync_pilot_features`.

---

## 9. Notifications (`notifications/types/campaigns.py`, feature `campaigns`)

| Key | Audience | Channels / limits |
| --- | --- | --- |
| `campaigns.enlisted` | actor | web, Discord DM; names untracked characters |
| `campaigns.gang_forming` ★ | active-in-last-hour with `notify_gangs` | web push, DM; 1 per pilot per 2 h; channel only while a strategic fleet is active |
| `campaigns.standing_fleet_needs_boss` ★ | enlisted online in campaign voice with `notify_standing_fleet` | web push, DM; 1 per pilot per 2 h |
| `campaigns.activity_nearby` ★ | `notify_activity`, not active, 5+ active | web push, DM; 1 per 6 h |
| `campaigns.streak_at_risk` ★ | `notify_streak`, nothing scored today | web push, DM at 20:00 prime time |
| `campaigns.fleet_scheduled` / `fleet_started` | `notify_fleets` | web, DM; idempotent per fleet |
| `campaigns.system_threshold` / `system_flipped` | `notify_thresholds`; flips also topic subscribers | web, DM staggered; flips add EVE mail |
| `campaigns.week_plan` | enlisted | channel post Thursdays: last week's result, this week's plan |
| `campaigns.weekly_awards` | enlisted | channel post + DM to winners |
| `campaigns.daily_digest` | `notify_digest` at `digest_hour` | web, DM; one per pilot per day |
| `campaigns.completed` | enlisted | web, DM, EVE mail |

★ pull-notifications: opt-in per type, hard cap three per pilot per day, prime-time quiet hours. Channel posts go to
`receive_campaign_pings` channels and `Campaign.discord_channel_id`. Campaign fleets get a campaign line in the fleet ping
embed. Adaptive cadence and dormant handling are Phase 2.

---

## 10. Frontend (Astro + htmx partials, server-rendered, `ErrorRefetch` everywhere)

- `/campaigns/` — active campaigns as cards (stacked system rows most contested first, Enlist / Join standing fleet / Open as
  prominent buttons, counts in a stat bar beneath), upcoming, past (live completed merged with the static retrospectives via
  `src/data/campaigns/index.ts`, `kind: 'live'`).
- `/campaigns/[slug]/`, in order: hero + stat bar + Right now strip · Today's orders **beside** This week's plan · Systems (three
  blocks each) · Sites + Gangs & fleets · Leaderboard · Killfeed · Timeline · Community (1b) · Scoreboard, awards · Roster and coverage.
- `/campaigns/[slug]/roster/` · `/account/campaigns/` (readiness) · `/campaigns/[slug]/manage/` (**works with name, systems and
  dates only**; optional depth: fits, order pool, commander's order, scoring, Discord/voice channels, donation corp and tag,
  insurgency stage; KPI panel for adoption, accuracy and ESI; Unmapped payouts view; weekly plan acceptance).
- Dialogs: Enlist (prefs + character checklist; button starts the token chain), Form a gang (four fields and a line), Take the
  standing fleet (confirm boss, advert name, voice), Report advantage (two fields).
- **Fleet tool changes**: `campaign` on the fleet create *and edit* forms (before, during or after, including closed fleets),
  preselected when opened from a campaign page and defaulting audience and location from it; a campaign badge on the fleet page,
  in the schedule post and in the fleet ping embed; kills and losses linked to the fleet instance on the fleet page; the enlist
  prompt to tracked members who join a campaign fleet and are not enlisted (one tap; also a DM if fleet alerts are on); fleet
  types `standing` and `gang`, created from the campaign page, never on the schedule.
- **Neocom**: `components/icons/CampaignsEvEIcon.astro` (in the repo, wrapping the existing CCP `64px-Sovereignty.png`; alt key
  `icon.campaigns.alt` added to `i18n/ui.ts`). Wire `<NeocomButton active={page.startsWith(translatePath('/campaigns'))}
  title='neocom.campaigns' description='campaigns.description' href={translatePath('/campaigns/')}><CampaignsEvEIcon /></NeocomButton>`
  gated on `campaigns.view`, add `neocom.campaigns` and `campaigns.description`, and the routes to `json/sitemap.json`. Show the
  button only once a campaign is scheduled or active.
- Files: `helpers/api.minmatar.org/campaigns.ts`, `helpers/fetching/campaigns.ts`, `pages/partials/campaign_*_component.astro`,
  `types/campaigns.ts`. Mobile: web push covers phones; Expo card in Phase 3.

---

## 11. Delivery

### 11.1 Stages and done-when

| Stage | Scope | Done when |
| --- | --- | --- |
| **Calibration week** | payout poll, recent-killmails poll, VP + operational-state snapshots and the ESI gate running in dev for 7 days on BearThatCares and tracked volunteers; board simulation on 30 days of production data; VP-per-plex measurement | coverage ≥ 99.5 % of ESI ground truth; latency p90 ≤ 15 min; 100 % of `FacWar*` rows stored and classified by kind; complex class ≥ 90 % high-confidence single-class on offensive plexes; every event code seen is in the table; top-twenty simulation contains site runners and gang hunters; no 429 on any group |
| **Phase 0 · Foundation** | app, models, features, `TokenType.CAMPAIGN`; ESI gate; VP columns + operational state; attribution hook, 48 h sweep, recent-killmails poll, LP-kill cross-check, `sources`; lifecycle; snapshot copy; payout poll, site attribution, event-code table + Unmapped payouts view; feed-event mirror + live hostile signal; advantage readings + state; enlist (three doors, token chain inside, per-character inclusion); readiness page; index + campaign page (hero, stat bar, strip, systems, sites, killfeed, timeline, roster, dialogs); fleet tool attribution + enlist prompt; Neocom; KPI panel | a scheduled campaign over three systems goes active on time; every enlisted kill/loss ≤ 5 min typical / 15 min p90 and every site within one poll; mails absent from zKillboard still arrive; a detected Amarr gang shows while active; **150 enlisted in week one, 50 % tracked by week two** |
| **Phase 1 · The undock loop** | arcs, weekly plan proposal and acceptance, today's orders from the gap, auto-drafted commander's order; streaks; live counters; standing fleet (type, take/join with ESI invites, boss watch); gangs (type, dialog, ping with strategic-fleet suppression, gang bonus); fits + SRP prefill; complex class inference validated; participant-days + weekly boards (metrics × scopes × periods); weekly close + six weekly awards; notification types with caps and quiet hours; Discord channel flag; zero-config manage page | a non-FC forms a gang in under a minute and two pilots get the ping; the standing fleet survives three boss handovers tracked; gang kills carry the bonus; a shared Medium plex shows once as a Medium; a week-five joiner can top week five; **standing-fleet uptime ≥ 80 % in prime time and one gang per day in week two; weekly active enlisted ≥ 60 % in week three** |
| **Phase 1b · Community layer** (ships during the first campaign) | `read_projects` on Director tokens, `EveCorporationProject` + contributors, poller, attribution, Projects card; donation tag/corp settings, hourly matcher, Donations card, Patron mark, prize payouts; `campaign` on posts, creator items and industry orders, Content and Supply cards, live-stream signal, Supply board, Voice of the Front and Quartermaster mentions | one funded corp project attributed and its contributors visible; donations with the tag appear within the hour and the pool line reconciles; a content item and a supply order attributed and shown |
| **Phase 2 · Recognition and depth** | phases with interim reports and frozen weights; gang impact cards; engagement ↔ gang linkage; heatmap + heatmap-weighted orders; efficiency board, Rookie of the Week, more awards; adaptive digest, dormant handling, lapsed nags; beacon/outpost self-tag; nightly participant re-resolution; close-out + retrospective generator; FC-programme prompt | a two-month campaign closes with phase and monthly reports already published and a retrospective from data alone |
| **Phase 3** | mobile card; propaganda share cards; campaign medals; supply objectives | — |

If week three misses its criteria, the next thing built is whatever the KPI panel says is broken, not Phase 2.

### 11.2 Build order and dependencies

```
Calibration harness ─┬─ ESI gate ──────────────┬─ payout poll ── site attribution ── complex inference
                     ├─ VP + operational state ─┤                                  └─ event-code table + admin view
                     └─ jump-graph fixture ─────┘
campaigns app + models ── TokenType.CAMPAIGN ── readiness page + chain ── enlist (three doors)
                       ├─ attribution hook ── sweep ── recent-killmails poll ── LP-kill cross-check
                       ├─ lifecycle ── arcs ── weekly plan ── orders ── commander's order draft
                       ├─ feed-event mirror ── strip (hostile signal) ── standing fleet ── gangs
                       ├─ advantage readings/state ── system cards
                       ├─ participant-days ── boards ── weekly close ── awards
                       └─ fleet tool: campaign on create/edit, badge, enlist prompt, types standing/gang
Phase 1b: read_projects on Director ── EveCorporationProject ── attribution ── cards; donation matcher; content/supply FKs
```

### 11.3 Tickets, in build order (each is one PR with tests; Phase 0 = 1–8, Phase 1 = 9–16, Phase 1b = 17–20)

0. Calibration harness: management commands for the polls, snapshots, gate and the accuracy, simulation and VP-per-plex reports.
1. `campaigns` app skeleton, models (§6.1 minus 1b and Phase 2), migrations, admin, feature keys; tests for attribution, outcome, enlistment and inclusion periods.
2. Shared ESI gate (Redis; `X-Ratelimit-*`, `X-Esi-Error-Limit-*`, 429 `Retry-After`), ETag on campaign polls, lapsed-token backoff, minute-bucketing with jitter, `eveonline` queue, ESI KPIs and alerts.
3. `TokenType.CAMPAIGN`, `scope_group()`, readiness page and endpoint, chained Update all, token chain inside enlist, redirect back to the campaign.
4. Feed: VP fields, operational state (SDE jump-graph fixture), campaign snapshot copy, threshold/flip events, 30-min poll.
5. Attribution hook + live counters + 48 h sweep + recent-killmails poll + LP-kill cross-check + `sources` + lifecycle; health alerts.
6. `EveCharacterFwLpPayout`, `FwPayoutEventCode`, `FacWar*` parser (tested on Appendix A), payout poll, site attribution, Unmapped payouts admin view; complex class inference with suppression and `CampaignSystemInsurgency`.
7. Feed-event mirror + live hostile signal; advantage readings, state task, Report dialog; API: list, detail, now, enlist (three doors), characters include/exclude, roster + coverage, killmails, sites, systems history, advantage, timeline.
8. Frontend: index, campaign page (hero, stat bar, strip, systems, sites, killfeed, timeline), roster page, dialogs, Neocom wiring; fleet tool: `campaign` on create/edit, badge, enlist prompt.
9. Arcs, weekly plan proposal/acceptance, orders from the gap, auto-drafted commander's order, orders and plan partials.
10. Standing fleet: type `standing`, `CampaignStandingFleet`, take/join with ESI invites, boss watch, uptime KPI, card.
11. Gangs: type `gang`, `campaigns.form_gang`, endpoint, dialog, ping with strategic-fleet suppression, gang bonus.
12. Fits link + SRP prefill; streaks with shields; visible-impact hint.
13. Participant-days, tier-weighted points, boards (metrics × scopes × periods), weekly close + weekly awards + mentions.
14. Notification types, Discord channel flag, digest, caps and quiet hours, week-plan post.
15. Zero-config manage page + KPI panel (adoption, accuracy, ESI, reading freshness, unmapped codes).
16. Pre-launch simulation report on production data; weight tuning; launch checklist.
17. Corporation projects: `read_projects` on Director tokens, models, poller through the gate, attribution, Projects card, events.
18. Donations: settings, hourly matcher, Donations card, Patron mark, prize payouts, exclusions.
19. Content: `campaign` on `EvePost`, `CampaignContent`, suggestions, Content card, live-stream signal on the strip.
20. Supply: `campaign` on `IndustryOrder`, Supply card, Supply board metric, Quartermaster mention, contribution-mix credit.

### 11.4 Rollout

1. **Calibration week** in dev with BearThatCares and volunteers; publish the report; fix gaps.
2. **Soft launch**: schedule the first campaign (Bleak Lands push) a week ahead; Neocom hidden until scheduled; brief the 21 FCs,
   Thinkspeak and Supply chiefs; FCs attribute their upcoming fleets; standing fleet advert agreed.
3. **Launch day**: campaign goes active at 11:00; commander's order and first weekly plan posted; fleet prompts enlist the first
   wave; readiness page linked in the announcement.
4. **Week one**: watch the KPI panel daily (enlisted, tracked, coverage, latency, 429s, unmapped codes); first Thursday awards post.
5. **Weeks two to four**: Phase 1b lands behind the same feature flag; launch criteria checked at week three.
6. **Rollback**: feature flag off hides the Neocom entry and pages; pollers stop; tables are durable and nothing is deleted.

### 11.5 Test strategy

Unit tests for attribution and outcome on synthetic mails and on the real Appendix A payouts; inclusion-period edge cases
(leave/rejoin, exclude/include mid-day); complex inference on the base-tier table with collisions and suppression; ESI gate
behaviour on 429, 4xx and error-budget exhaustion with a mocked ESI; weekly plan proposal on synthetic momentum series;
order generation splits; board sums from participant-days; the simulation harness against production read-only data.
Live ESI is blocked under tests as today.

---

## 12. Open questions, defaults if unanswered

| Question | Who | Default if unanswered at build time |
| --- | --- | --- |
| Which battlefield did BearThatCares run (character, date, system)? | Kaleb | event 359 stays unconfirmed and unscored; the admin view tags the first battlefield seen |
| Do beacons and outposts share code 516? | Kaleb (deploy one on a tracked character, or read the 11 Sep 14:34 Hadozeko wording) | 10,000-LP 516 payouts are labelled "advantage site" |
| Which corporation and wallet division receive donations? | Kaleb / leadership | the campaign creator's corporation, division 1 |
| Standing fleet advert name and voice channel convention | FCs | "MINMATAR FLEET · <campaign name>", campaign voice channel 1 |
| Who may take the standing fleet? | leadership | any enlisted pilot |
| VP per complex class at a given advantage | calibration week | measured; editable table |
| Site-runner population | calibration week | reported |

## 13. Risks

| Risk | Mitigation |
| --- | --- |
| Token adoption for site credit | token chain inside the first enlist; readiness page; coverage on hero, response, digest, KPI panel |
| Fleet blobs own the board | kill points scale with pilots on the mail; contribution-mix bonus; pre-launch simulation |
| Nudges become noise | per-type opt-in, 3/day cap, quiet hours; opt-out rate on the KPI panel |
| Standing fleet needs an in-game boss | any enlisted pilot can take it; boss re-discovery; "needs a boss" ping; uptime KPI |
| `form_gang` widens who starts tracked fleets | gangs never on the schedule or audience-pinged; DMs suppressed during strategic fleets |
| Order and points farming | same rules as scoring; kill-with-enlisted needs a non-enlisted victim; pods never score; site soft cap |
| Complex class inference | tier collisions, untracked pilots inside, snapshot staleness, suppression; points follow the tier, unknown scores as Scout, low-confidence marked, validated first |
| Advantage has no API; readings can be gamed | exact contribution from payouts; consensus, staleness, outlier holds; capped points; mute after three holds; manager override |
| Mails not on zKillboard | measured 1 in 203; recent-killmails poll covers every included character; `on_zkillboard=false` avoids dead links |
| ESI error limit | the gate never polls a bad token and pauses at error-limit-remain < 20 |
| Scheduled before start is a hard rule | manage copy + lifecycle guard; nothing is imported after the fact |
| Feed clusters are heuristics | labelled "detected", never scoring input |
| Long-campaign fatigue | weekly boards and repeatable awards; weekly streak mode; phases and adaptive cadence in Phase 2 |
| Donation tag typos; donations as pay-to-win | manual attribution; copyable instruction; recognition only, never points |
| Corp projects need director re-auth | one scope; Projects card shows "no director token" per corp |
| Committed credentials | the read-only production DB password is committed in `app/settings.py`; outside scope, should be rotated |

---

## Appendix A. Notification samples (BearThatCares, 2026-09-18)

```
FacWarLPPayoutEvent  2026-09-10T22:22Z      FacWarLPPayoutEvent  2026-09-07T17:12Z      FacWarLPPayoutEvent  2026-08-27T01:02Z
amount: 31                                  amount: 10000                               amount: 52500
charRefID: 3019201                          charRefID: null                             charRefID: null
corpID: 1000182                             corpID: 1000182                             corpID: 1000182
event: 371          (complex capture)       event: 516     (RP / beacon / outpost)      event: 359     (unconfirmed large payout)
itemRefID: 57774    (site id)               itemRefID: null                             itemRefID: 14030
locationID: 30002541 (Dal)                  locationID: 30003069 (Kamela)               locationID: 30003070 (Sosala)

FacWarLPPayoutKill   2026-08-24T23:49Z      FacWarLPDisqualifiedKill  2026-08-29T19:55Z
amount: 365                                 amount: 0
charRefID: 95511674 (victim)                charRefID: 96355520
corpID: 1000182                             corpID: 1000182
event: 367          (kill)                  disqualificationType: 10
itemRefID: 137966392 (killmail id)          event: 367
locationID: 30002541                        itemRefID: 138074920
                                            locationID: 30003069
```

## Appendix B. Dev testing

Live ESI works from `backend/` when sourcing `backend/.env` (not `standalone.env`, whose SSO credentials are placeholders) with
the dev DB overrides. BearThatCares (`634915984`) holds the notifications scope. The `production_readonly` database alias
allows read-only measurement against production. Under tests, live ESI is blocked by `live_esi_allowed()`.

## Appendix C. Product review log (2026-09-19)

Fleet alliance → Join first, `fleet_attend`/`fleet_kill` orders · Fleet blobs → kill and ISK points scale with pilots on the mail,
contribution-mix, simulation on production data · Pointless plexing → defensive plex orders only at enemy contest ≥ 10 % ·
Off-hours → ×1.25 03:00–14:00 UTC · Strategic fleets → gang DMs suppressed · Volunteer leadership → zero-config, auto-drafted
commander's order, automatic weekly awards, auto-proposed weekly plan · Multiboxers → site soft cap · Fewer doors → Undock solo
scrolls to orders; self-tag, efficiency board, Rookie, heatmap-weighted orders to Phase 2; fits card folded into orders; LFG replaced
by the standing fleet · Awards → six weekly + three campaign · Launch criteria in Phase 0 and Phase 1 done-when.
