---
name: eve-alliance-recruitment-scout
description: >-
  Scout Reddit and EVE forums for pilots looking for corporations, route them to
  the right alliance corp using public API data, and draft short human outreach.
  Use when the user asks to find recruitment prospects, scan r/evejobs, check
  LFC posts, pull forum recruitment threads, scout for corp seekers, or run the
  alliance recruitment scout.
---

# EVE Alliance Recruitment Scout

Find pilots **looking for a corporation** (not corps recruiting), check whether
your alliance already replied, route to the best corp, and draft short human
outreach.

**This is an agent skill first.** The durable, improving part is this document
plus [voice.md](voice.md) (how a reply sounds) and [examples.md](examples.md)
(routing and send-shape corrections from past runs). Add to `examples.md`
after sending outreach; add to `voice.md` only when a reply that sounded like a
person is worth copying.

`scripts/` holds **optional single-purpose fetchers** the agent can mix and match.
They do not route corps or draft messages. You can also hit endpoints and browse
directly — scripts are convenience for Reddit OAuth and pagination.

Configurable for any alliance. The reference implementation uses
[Minmatar Fleet Alliance](https://my.minmatar.org/) and `api.minmatar.org`.

## Quick start

**Agent workflow (primary):** follow the two phases below. Read corp bios, scan
sources, judge fit, then read `voice.md` and draft.

**Optional fetchers** (run only what you need):

```bash
cd .claude/skills/fl33t-recruitment-scout
pip install -r requirements.txt

# Reddit OAuth — load from backend/.env (do not commit these values)
set -a && source ../../../backend/.env && set +a

python scripts/fetch_corporations.py --json
python scripts/fetch_recruitment_ads.py --days 30 --json
python scripts/fetch_proof_media.py --days 45 --json
python scripts/fetch_reddit.py --days 7 --json
python scripts/fetch_forums.py --days 7 --json

# Tracked links (needs MINMATAR_API_TOKEN, see "Tracked links" below)
python scripts/track_outreach.py stats --days 30
python scripts/track_outreach.py register --surface evejobs \
  --thread https://www.reddit.com/r/evejobs/comments/... --prospect u/name --seat BNSQ
```

Reddit credentials (`REDDIT_CLIENT_ID`, `REDDIT_SECRET`, `REDDIT_USERNAME`,
`REDDIT_PASSWORD`) live in `backend/.env`. Needed for `u/MinmatarFleet` ad
history and reliable Reddit comment reads. Corporation data loads from the public
API without them. `MINMATAR_API_TOKEN` (also in `backend/.env`, local only) is
your `auth_token` cookie from my.minmatar.org; it needs the `recruitment.scout`
feature.

See [README.md](README.md) for setup.

## Workflow

Complete **pre-scout** before searching for prospects. **You** (the agent) own
filtering, responded detection, corp routing, and outreach. The script only helps
gather raw posts if you choose to run it.

```
Task Progress:
- [ ] Pre-scout: load corporation profiles from public API
- [ ] Pre-scout: review u/MinmatarFleet ads (past 30 days)
- [ ] Pre-scout: gather recent AARs / capital videos (u/BearThatCares)
- [ ] Pre-scout: read tracked-link clicks for the last 30 days (track_outreach.py stats)
- [ ] Scout: find player LFC posts (past 7 days) — browse, search, or optional script
- [ ] Read each thread; decide responded vs open
- [ ] Route each open prospect to one primary corp (from pre-scout bios)
- [ ] Register each open thread for a tracking code (track_outreach.py register)
- [ ] Read voice.md, then draft outreach with tracked hrefs
- [ ] Present the four-part output (overview, already replied, need to reply, copy-pastable replies)
```

### What improves over time

| Improves with the skill | Should NOT live in Python |
|-------------------------|---------------------------|
| Corp routing judgment | Keyword scoring, static corp tables |
| Outreach voice and length | Message templates in code |
| Spotting LFC vs recruiting ads | `"lf corp"` triggers, regex lists |
| Responded detection | Hardcoded marker strings |
| When to link ads vs plain discord | Hardcoded per-corp rules |
| New corp focus or requirements | Config that duplicates the API |

Update [examples.md](examples.md) after sending outreach: paste what was sent and
one plain sentence on what changed. That is the feedback loop for routing and
send-shape. Voice lives in [voice.md](voice.md); do not pre-fill templates.

### Data scripts (pick what you need)

| Script | Purpose | Needs Reddit OAuth? |
|--------|---------|---------------------|
| `fetch_corporations.py` | Corp bios, timezones, requirements from API | No |
| `fetch_recruitment_ads.py` | `u/MinmatarFleet` submissions (default 30 days) | Yes |
| `fetch_proof_media.py` | `u/BearThatCares` AARs / capital videos (default 45 days) | Yes |
| `fetch_reddit.py` | Raw `/new` from `r/evejobs`, `r/eve` (default 7 days) | Yes |
| `fetch_forums.py` | Recruitment-center latest topics (default 7 days) | No |
| `match_corp_ads.py` | Map ad URLs to corp names (optional convenience) | No |
| `track_outreach.py` | `register` a reply's tracking code; `stats` for clicks per reply | No (`MINMATAR_API_TOKEN`) |

All scripts accept `--json` and `--config path/to/config.json`. `fetch_reddit.py`
also accepts `--subreddit eve` (repeatable) to override config.

Example: map ads after fetching both:

```bash
python scripts/fetch_corporations.py --json > /tmp/corps.json
python scripts/fetch_recruitment_ads.py --json > /tmp/ads.json
python scripts/match_corp_ads.py --corporations /tmp/corps.json --ads /tmp/ads.json --json
```

You can skip any script and use curl, browser, or Reddit search instead. Run
`fetch_reddit.py` only, or forums only, or browse manually — whatever fits the task.

### Phase 1: Pre-scout (context)

Gather alliance context **before** searching for prospects.

#### 1a. Corporation profiles (public API)

Fetch corporation data from your configured API:

```
GET {api_base_url}/eveonline/corporations/corporations?corporation_type=alliance
GET {api_base_url}/eveonline/corporations/corporations?corporation_type=associate
```

Default: `https://api.minmatar.org/api/eveonline/corporations/corporations`

Read each corp's `introduction`, `biography`, `timezones`, and `requirements`.
Build a mental routing map: which corp fits which pilot profile. Do not rely on
hardcoded corp lists when the API has fresher data.

OpenAPI docs: https://api.minmatar.org/api/docs

#### 1b. Recent recruitment ads (Reddit)

Fetch posts from **`u/MinmatarFleet`** for the **past 30 days** (default
`--pre-scout-days 30`). This is the alliance recruitment Reddit account; it posts
corp ads on `r/evejobs` (Rattini, Soltech, Dark Tribe, Academy,
Banshee, Solaris, FOSFO, Extraction, etc.). **Only route to corps on the
recruiter layout below.** Corps leave the alliance (e.g. Straylight is gone).
FOSFO is on that layout. Name it and link the live `u/MinmatarFleet` ad even
when the corporations API has not listed it yet.

```
https://www.reddit.com/user/MinmatarFleet/submitted/
```

The script fetches these via Reddit OAuth. Load credentials from `backend/.env`:

- `REDDIT_CLIENT_ID`
- `REDDIT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`

Map ad titles to corps by matching API corporation names against ad titles.
These URLs go into outreach messages when linking to a specific corp ad.

Review what Minmatar Fleet has been recruiting for recently. Match outreach tone
and corp focus to active ads, not stale positioning.

#### 1c. Recent AARs and capital videos (proof media)

Gather fresh **battle reports and capital / big-fight videos** to use in
outreach — especially Rattini (caps / multi-box vets) and WH→FW or casual-null
redirects. Primary source: **`u/BearThatCares`** Reddit submissions (default
lookback **45 days**).

```
https://www.reddit.com/user/BearThatCares/submitted/
```

Optional script:

```bash
python scripts/fetch_proof_media.py --days 45 --json
```

Config: `reddit.proof_accounts` (default `["BearThatCares"]`). Override with
`--account OtherUser` (repeatable).

**You** pick which **extra** AAR to add. Prefer the newest billion-ISK-class
fight over old or off-topic posts. After each scout, replace the Current kit
table below when a bigger or newer AAR lands — do not keep a graveyard of six
old reports.

**Proof closes (required stack):**

| Layer | Resource | URL | When |
|-------|----------|-----|------|
| **Always on r/evejobs and forums** | **Bring Fun Shit** | `https://youtu.be/7-eGTtq9vWo` | **Every r/evejobs and forum send.** Mining, MFA, no-PvP, WH redirect, named corp, saturated thread. Own block. **Not on r/eve.** |
| **Also mining / industry** | **Rock Hoppin'** (Extraction Company) | `https://youtu.be/XCApG7Pt6m4` | Extraction, MFA rock fleets, highsec bulwark miners, corp-merge industry, on r/evejobs and forums. **In addition to** Bring Fun Shit, not instead of it. Own block after BFS. **Not on r/eve.** |
| **Also big fight** | Newest AAR in the Current kit | see table | PvP/FW, caps, Rattini, WH→FW, “where’s the action,” on r/evejobs and forums. One AAR max unless they asked for capitals — then you may add the cap-feed AAR too. Never a substitute for Bring Fun Shit there. On r/eve, this AAR is the whole reply when the thread is about fights. |

Do not dump every AAR into every message. On r/evejobs and forums, do not skip
Bring Fun Shit because an AAR or Rock Hoppin' is already in the reply. On r/eve,
skip that video stack. The reply is one content piece: an AAR, the warzone
report, or the Amamake market report.

#### Current kit (update from pre-scout 1c)

Replace rows when a new mega-fight AAR posts. URLs also live in `config.json`
(`proof_videos`, `proof_aars`, `proof_pages`).

| Kind | Title | URL | Use |
|------|-------|-----|-----|
| Video | Bring Fun Shit | `https://youtu.be/7-eGTtq9vWo` | Every r/evejobs and forum send |
| Video | Rock Hoppin' | `https://youtu.be/XCApG7Pt6m4` | Mining/industry extra |
| AAR | 625B down in Amamake (27 Sep YC128) | `https://www.reddit.com/r/Eve/comments/1wr8ohf/aar_625b_down_in_amamake/` | Default extra AAR (newest big fight). r/eve plug when the thread is about fights. |
| AAR | 700B down in Ahbazon (1 Aug YC128) | `https://www.reddit.com/r/Eve/comments/1vcyik3/aar_700b_down_in_ahbazon/` | Caps / Rattini / the dread-feed joke. r/eve plug when they asked about capitals. |
| Site | Monthly Warzone Report | `https://my.minmatar.org/warzone/` | Forums onebox / casual-null / action-location threads. r/eve plug when they ask how the war is going. |
| Site | Amamake market report | `https://my.minmatar.org/amamake-market/` | r/eve plug when the ask is mining, market, ISK, or the station economy. |
| Site | Corporation directory | `https://my.minmatar.org/alliance/corporations/` | Dual-route, self-serve bios |
| Site | Freight contracts history | `https://my.minmatar.org/market/freight/contracts/history/` | Hauler learning PvP (side proof, not MFA routing) |
| Site | Auga siege (YC128) | `https://my.minmatar.org/alliance/campaigns/auga-yc128/` | Optional older siege page; prefer Kamela AAR + warzone report when both fit |

### Phase 2: Scout (prospects)

Find posts from the **past 7 days** (or user-specified window) where a **player**
is looking for a corporation — not where a corp is recruiting.

**Sources:**

| Source | How |
|--------|-----|
| r/evejobs | `/new`, or search however you think will surface LFC posts. Full recruitment reply. |
| r/eve | Same; some pilots post outside evejobs. Reply with one content piece (warzone report, Amamake market report, or an AAR). The corp pitch stays on r/evejobs and the forums. |
| EVE Forums | Recruitment Center latest, or search the category |

Search terms and browsing strategy are your call. Use judgment, not a fixed
keyword checklist. A post counts if the author is clearly a pilot seeking a home.

**Optional:** run individual scripts from `scripts/` (see table above). Output is
**unfiltered** — you triage every candidate yourself.

**No database access required.** Corporation data comes from the public API.

### Triage prospects (your judgment)

**Include** when a player is looking for a corp, home, alliance, or community to
join — read the title and body, do not pattern-match keywords.

**Exclude from named-corp routing** when:

- A corp or alliance is recruiting members (the recruiter posted, not the pilot)
- The pilot explicitly does not want a corporation
- The post is outside the lookback window
- It is your own alliance recruitment post (e.g. `Recruiting corporations who want help growing!` from `u/MinmatarFleet`)

**Poor corp fit ≠ silent skip.** Still draft outreach (section 3 and a copy block
in section 4) when:

- **WH-only seekers** — blunt FW redirect (session ISK/kills, no scanning)
  unless they are USTZ new or early-intermediate with wormhole use on the side,
  which is SOEXD. Bring Fun Shit always; optional WH-operator credibility. Add
  the newest kit AAR when the thread has room for a second proof link. Do not force
  SLTAR or ARAT into a jspace-locked thread unless they leave lowsec open.
- **Sov-null mining / industry seekers** — highsec bulwark + Extraction fleet density;
  never “we have sov too.”
- **Prefer-null casual / leisure PvP** — FW proof BR redirect (see examples).

**True no-reply** is rare: hard nullbloc lifestyle lock (dedicated sov Indy/CRAB +
PAPs + supers with no opening past null) may stay unanswered — note it, do not invent
a null pitch. Same for **Discord-impossible** seekers (invite banned in their
country) when every corp on the API requires Discord; do not invent Mumble/TS.

When unsure, open the thread and read it.

### Detect "Responded"

Open the thread. Mark **Y** if your alliance already reached out — a recruiter
reply, a corp pitch mentioning Minmatar Fleet / FL33T / `discord.gg/minmatar`, or
any clear prior outreach from your side.

A stranger saying “try the Amarr-Minmatar warzone / Amamake” is **not** Responded.
Need a FL33T recruiter, a named alliance corp, or `discord.gg/minmatar`.

**Already responded → separate table. Do not draft new outreach.**

### Route to the right corp

**Source of truth:** pre-scout data only. Read corporation profiles from the API
(`introduction`, `biography`, `timezones`, `requirements`) and match prospects
against recent `u/MinmatarFleet` ads. Corps change over time.

This is your judgment call. Read the pilot's post, read the corp bios, pick one
primary corp. Poor WH or sov-mining fit still gets a redirect draft in sections
3 and 4, not a silent skip.

Describe each corp by what it offers. Avoid ranking language (“not X material,”
“weaker fit for Y”) in notes or outreach — alliance corps reading this should
recognize complementary seats, not a pecking order.

**Principles** (apply using current `requirements` fields from the API):

- Check each corp's `requirements` before routing. A corp that expects active
  fleet participation or leadership roles is a poor fit for casual or patchy
  playtime unless the pilot explicitly wants that commitment.
- Industry-primary pilots belong in **Minmatar Fleet Associates (MFA)** associate
  corps, not FW alliance corps. MFA lives in **highsec bulwark systems** with
  **lowsec excursions** — pitch that, not FW daily life. Mention a PvP corp only
  as an optional side path, not the primary pitch.
- **Academy is Omega-only** (API `requirements`). Alpha seekers go MFA / highsec
  PvE, not L3ARN.

One primary corp per prospect. Optional one-liner for a graduate path or
bigger/smaller corp in the same alliance — name only, no ad link. Use
`(same alliance)` when naming a secondary corp (e.g. `Banshee Squadron
(same alliance)` or `Rattini Tribe (same alliance)`).

**FL33T routing map** (recruiter layout; overrides API timezone text and older
“who is the newbro corp” notes when they conflict). Tickers are how recruiters
talk. Use the API or ad name in outreach.

Two axes, then timezone only where the layout has one:

| Axis | Seats |
|------|--------|
| Small gang, veterans | **TDT** (USTZ), **FOSFO** (EUTZ) |
| New / early intermediate | **SOEXD** (USTZ, wormhole on the side), **BNSQ** (EUTZ) |
| Institutional | **L3ARN** (new), **SLTAR** (intermediate / veteran) |
| Capitals / many characters | **ARAT** (veterans) |

| Ticker | API / ad name | Route when… |
|--------|---------------|-------------|
| **TDT** | The Dark Tribe | **USTZ** veterans who want **small gang**. Not the new-player door. API SP / killboard lines do not turn this into a newbro corp. |
| **FOSFO** | FOSFO (live `u/MinmatarFleet` ad) | **EUTZ** veterans who want **small gang**. Route it from this layout and link the live ad even if the corporations API has not listed the corp yet. |
| **SOEXD** | Solaris Expeditionary Corps | **USTZ** **new or early-intermediate** pilots, with **wormhole use on the side** of faction warfare. Not the seat for veteran hole-only seekers, and not “any USTZ player.” |
| **BNSQ** | Banshee Squadron | **EUTZ** **new or early-intermediate** pilots. The small EUTZ learning seat. Academy is the institutional new-player door when they want the school, not this crew. |
| **L3ARN** | Minmatar Fleet Academy | **New players, institutional.** The structured learn-by-undocking corp. All timezones. Omega required. A returning pilot who has barely fought is still this seat. Alphas go MFA, not here. |
| **SLTAR** | Soltech Armada | **Intermediate or veteran, institutional.** The organized faction-warfare corp for people past brand-new who are not asking for a small-gang specialty or for capitals. Timezone does not decide this seat. Do not use it as the filler when the post is thin. |
| **ARAT** | Rattini Tribe | **Veterans** flying **multiple characters and/or capitals**. Not the default veteran corp. One character and no capital ask stays SLTAR, TDT, or FOSFO. |

Additional principles:

- Pick the seat from experience first (new / early intermediate / intermediate / veteran), then style (small gang, institutional, capitals), then timezone where the layout has one.
- **New, no timezone, wants teaching:** L3ARN. Missing timezone is not a SLTAR signal.
- **EUTZ new or early intermediate:** BNSQ. **USTZ new or early intermediate,** especially with wormhole play beside faction warfare: SOEXD.
- **EUTZ veteran small gang:** FOSFO. **USTZ veteran small gang:** TDT.
- **Intermediate or veteran, wants the organized corp, no small-gang specialty, no capital ask:** SLTAR.
- **Industry-primary:** MFA associate corps primary. Base in highsec bulwark systems, lowsec excursions when people want out. PvP corp is a side note only. Name **Minmatar Extraction Company** (and its Amo mining ad) when they want organized mining fleets; the MFA network on `discord.gg/minmatar` for general industry/PvE. Do not name a Discord person. Dual accounts (mining main + PvP alt) can split Extraction + the FW seat that matches the combat character. On forums, linking `my.minmatar.org/alliance/corporations/` works when dual-routing. Small industry **corps** seeking a null alliance home still get Extraction (fleet density / ore volume). Close with **Bring Fun Shit then Rock Hoppin'** (two blocks).
- **Ex-FL33T returning:** if they already left Rattini and are not asking for dreads or a pile of characters, route **SLTAR** rather than sending them back to ARAT.
- **Caps / multi-box veterans:** ARAT. Unused capital + learning lowsec → ARAT (own the dread-feed joke). Close with Bring Fun Shit, then the cap-feed AAR from the Current kit (Ahbazon 700B until a newer cap brawl replaces it). **Straylight is not in the alliance** — never route or link there.
- **WH-only veterans, or jspace with no USTZ new/early-intermediate angle:** nameless FW redirect plus Bring Fun Shit and the newest kit AAR. Do not close that redirect with Rock Hoppin'. SOEXD is for USTZ new and early-intermediate pilots who still want a hole on the side.
- **Alliance positioning:** we are a **faction warfare** alliance. Daily content is FW and lowsec small gang. Do not pitch nullsec, sovereignty, null ratting, structure timers, or bloc null. If OP wants dedicated sov-null mining, pitch highsec bulwarks / Extraction instead — never "we have sov too." If OP wants dedicated nullbloc PAP/CRAB lifestyle with no industry-or-FW opening, leave unanswered rather than inventing a null pitch.
- **Proof closes above are for r/evejobs and the forums.** On r/eve, keep the seat in section 3, then send the content plug instead of the ad and video stack.

### Draft outreach

Read [voice.md](voice.md) now, then draft. It is the voice guide: who is
talking, real replies that sounded like a person next to scout drafts that
did not, and the tells to catch before pasting. This section is only the
send-shape: how long, and where the links go on each surface.

The pitch is **one short paragraph, two sentences by default**, readable on
a phone without scrolling. One sentence when the thread is crowded, three
only when they asked something a second sentence cannot cover. Proof videos
and forum oneboxes are **separate blocks**, never glued onto the pitch.

#### Send-shape (required)

| Surface | The pitch | After the pitch |
|---------|-----------|-----------------|
| **r/evejobs** | No URLs inside it. | Blank line, the line `Some links`, then a markdown bullet list. Discord and my.minmatar.org bullets use tracked hrefs. See section 4. |
| **r/eve** | No pitch. One or two sentences that answer the thread. No corp name. | Exactly one content URL on its own line. See below. |
| **Forums** | The ad URL as bare text and `discord.gg/minmatar` as a tracked link in the last sentence. | Each proof URL on its own line so Discourse embeds it: Bring Fun Shit, Rock Hoppin' when mining, one AAR. No bold YouTube URLs. No `Some links` list. |

#### r/eve (content plug)

r/eve is a discussion subreddit. The people in the thread are there for the
post, so a corporation name, an r/evejobs ad, or a Discord invite reads as a
recruiter who wandered in. Answer the thread like a pilot pointing at a
writeup, then hand them one piece of content. Section 3 still names the seat
from the routing map so the recruiter knows the direction. The copy block is
the plug.

- One or two sentences that answer their question and name the place
  (Amamake, the Amarr-Minmatar warzone, highsec bulwarks). It can say the
  writeup is ours ("our monthly warzone report"). That is the tie back.
- Do not name a corporation, describe a roster, or say we are recruiting.
  Never link an r/evejobs ad, Discord, Bring Fun Shit, or Rock Hoppin'.
- Exactly one URL, on its own line, no label, no bullets. The URL is the
  comment. Do not skip it.
- Pick the piece that matches the thread:
  - Fights, faction warfare, "where's the action", returning to shoot: the
    newest kit AAR. Capitals: the cap-feed AAR.
  - How the war is going, occupancy, a returning pilot asking what changed:
    the monthly warzone report.
  - Mining, market, ISK, industry, the station economy: the Amamake market
    report.
- Warzone and Amamake links use tracked hrefs. AARs stay bare Reddit URLs.

```
[one or two sentences that answer the thread and point at the piece]

[one URL alone]
```

#### Before you present

Read every draft in the run back to back against the "Tells to catch" list
in `voice.md`. Two drafts that open the same way or share a phrase means one
gets rewritten. Then check the proof stack: r/evejobs and forum drafts
include Bring Fun Shit; mining and industry on those surfaces also include
Rock Hoppin'; PvP, FW, caps and redirects there add the newest kit AAR when
the thread has room. r/eve drafts stay one or two sentences plus one URL.

### Tracked links

Discord and my.minmatar.org links carry a per-reply code so recruiters can see
which replies get clicked. Nothing else is tracked: corp ads, AARs, YouTube and
any other link stay exactly as they are.

1. After routing, register every open thread you will draft for:
   `python scripts/track_outreach.py register --surface evejobs|eve|forums
   --thread <thread url> --prospect <their name> --seat <ticker, MFA, FW redirect>`.
   It prints the code and a tracked URL per target. Drafting the same thread
   again on a later run returns the same code.
2. The **visible text stays the real URL**. Only the href changes to
   `https://my.minmatar.org/go/<code>/<target>`:

   | Link | Write it as |
   |------|-------------|
   | Discord | `[discord.gg/minmatar](https://my.minmatar.org/go/<code>/discord)` |
   | Learning | `[https://my.minmatar.org/learning/](https://my.minmatar.org/go/<code>/learning)` |
   | Corp directory | `[https://my.minmatar.org/alliance/corporations/](https://my.minmatar.org/go/<code>/corporations)` |
   | Warzone report | `[https://my.minmatar.org/warzone/](https://my.minmatar.org/go/<code>/warzone)` |
   | Amamake market report | `[https://my.minmatar.org/amamake-market/](https://my.minmatar.org/go/<code>/amamake)` |
   | Freight history | `[https://my.minmatar.org/market/freight/contracts/history/](https://my.minmatar.org/go/<code>/freight)` |

   Targets live in `config.json` → `tracked_links.targets`. A page with no
   target there (the Auga siege page, for one) stays a plain link.
3. One code per reply. Never reuse a code across threads, and never put a
   tracked link in a corp ad, AAR or video slot.
4. **No token, no tracking.** If `MINMATAR_API_TOKEN` is missing or the
   register call fails, draft with the plain links and say so in section 1.
   Never invent a code.

One trade-off: on the forums a masked link shows as a plain link, not a
onebox card. That is fine for the corp directory and warzone report. Bring Fun
Shit, Rock Hoppin' and AARs keep their bare URLs so they still embed.

Bots that unfurl a link (Discourse onebox, Reddit, Discord) are recorded but not
counted, so posting a reply does not count as a click.

### Present output

Four sections, in this order. Sections 1–3 are for reading. Section 4 is what a
recruiter copies. Do not put the pitch inside a markdown table.

#### 1. Overview of the results

Short prose: lookback window, how many player posts, how many already replied,
how many still need a reply, how many true no-replies. Name the corp seats used
this run in one sentence. Flag a kit change (new AAR) here if one happened.

Then one or two sentences from `track_outreach.py stats --days 30`: replies per
surface, how many got any click, how many clicked Discord, and which seats or
openings drew clicks. Note it when tracking was skipped this run (no token).

#### 2. Overview of who we've already replied to

One line per thread. Title, who replied (Reddit username or forum username),
corp they pitched if they named one, link. No new draft.

#### 3. Overview of who we need to reply to

One line per open thread. Title, seat (ticker plus corp name), why that seat in
a few words, link. Industry redirects and nameless FW redirects belong here too.
True no-replies get their own short list under this section, not mixed into the
reply list.

#### 4. Copy-pastable replies

One block per open thread, in the same order as section 3. Each block:

1. A heading the recruiter does not paste: title, seat, `r/evejobs`, `r/eve`, or `Forums`, tracking code, link to the thread.
2. A fenced code block they can copy whole.

**r/evejobs** (what actually gets sent):

- Pitch is one paragraph and contains no URLs.
- Blank line, then the line `Some links`, then a markdown bullet list.
- Each bullet is a markdown link whose visible text is the URL: `* [https://…](https://…)` . For my.minmatar.org pages the href is the tracked link: `* [https://my.minmatar.org/learning/](https://my.minmatar.org/go/<code>/learning)` .
- Discord is `* [discord.gg/minmatar](https://my.minmatar.org/go/<code>/discord)` (plain `http://discord.gg/minmatar` only when tracking was skipped).
- Do not name a Discord person in the pitch or the link list. Discord in the list is the contact.
- Brand-new teach-me Academy posts put `https://my.minmatar.org/learning/` first in the list and skip the AAR.
- Other Academy / PvP posts: ad, discord, Bring Fun Shit, then one AAR when the kit says so.
- Mining / industry posts: Bring Fun Shit, the mining ad, Rock Hoppin', discord. Order can put discord first when the ask is a corp home rather than “how do I mine.”

**r/eve** (what actually gets sent):

- One or two sentences, no URLs inside them. Answer the thread. Do not name a corp.
- Blank line, then exactly one URL. No `Some links`, no bullets, no r/evejobs ad, no Discord, no Bring Fun Shit, no Rock Hoppin'.
- Fights and "where's the action": the newest kit AAR, bare. Capitals: the cap-feed AAR, bare.
- How the war is going: `[https://my.minmatar.org/warzone/](https://my.minmatar.org/go/<code>/warzone)`.
- Mining, market, or ISK: `[https://my.minmatar.org/amamake-market/](https://my.minmatar.org/go/<code>/amamake)`.
- Register the thread with `--surface eve`. An AAR stays a bare Reddit URL. A site report uses the tracked href.

**Forums** (bare URLs, so Discourse oneboxes):

- Pitch is one paragraph. The corp ad URL sits in the last sentence as bare text. `discord.gg/minmatar` sits there too as the one markdown link, `[discord.gg/minmatar](https://my.minmatar.org/go/<code>/discord)`. No other markdown links, no bold. Do not add an "ask for" name.
- Blank line, then each proof URL on its own line: Bring Fun Shit, Rock Hoppin' when mining, then one AAR when the kit says so.
- Named corp with no ad: tracked `discord.gg/minmatar` in the pitch, then `[https://my.minmatar.org/alliance/corporations/](https://my.minmatar.org/go/<code>/corporations)` on its own line before the videos.
- A full `https://www.reddit.com/r/evejobs/comments/...` URL oneboxes as Reddit. A `/r/evejobs/s/` shortlink does too.

Do **not** dump WH-only or sov-mining seekers into a “skipped, no message” list.
They get a seat in section 3 and a copy block in section 4 (`FW redirect` or
`Minmatar Extraction Company`).

After section 4, a short roster of live ad URLs is optional.

## Configuration

`config.json` tells the optional collector **where to fetch** — API URL, subreddits,
forum category, `u/MinmatarFleet`. It does not encode triage rules, response
markers, or routing. Those live in this skill.

| Field | Purpose |
|-------|---------|
| `api_base_url` | Corporation API base |
| `reddit.recruitment_account` | Recruitment Reddit user (`MinmatarFleet`) |
| `reddit.proof_accounts` | Reddit users for AAR / capital video pre-scout (`BearThatCares`) |
| `reddit.subreddits` | Subreddits for raw `/new` fetch |
| `forums.recruitment_center_category` | Forum category slug |
| `discord_invite` | For outreach closers (skill only) |
| `tracked_links.targets` | Link targets for `my.minmatar.org/go/<code>/<target>`; must match `frontend/app/src/json/scout-links.json` |
| `proof_videos.always` | Bring Fun Shit — required on every r/evejobs and forum send; not on r/eve |
| `proof_videos.mining` | Rock Hoppin' — extra close for mining/industry |
| `proof_aars` | Current billion-ISK AARs (newest first); rotate when a new one posts |
| `proof_pages` | Warzone report, Amamake market report, corp directory, freight history, optional siege pages |

## Additional resources

- Past outreach learnings (add as you go): [examples.md](examples.md)
- Data scripts: [scripts/](scripts/)
- Setup: [README.md](README.md)
