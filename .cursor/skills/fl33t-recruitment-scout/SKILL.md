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
this tool or another alliance recruiter already replied, route to the best
corp, pick the video that fits the post, and draft short human outreach.

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
python scripts/fetch_videos.py --json
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
- [ ] Pre-scout: list the newest alliance YouTube videos (fetch_videos.py) and refresh the video shelf
- [ ] Pre-scout: read tracked-link clicks for the last 30 days (track_outreach.py stats)
- [ ] Scout: find player LFC posts (past 7 days) — browse, search, or optional script
- [ ] Read each thread; decide ours, another alliance recruiter, or open
- [ ] Route every prospect that is not ours to one primary corp (from pre-scout bios)
- [ ] Another recruiter replied: compare their pitch with the routed seat; draft a second reply unless theirs already covers it
- [ ] Pick the video for each reply from the shelf, matched to what the post asks for
- [ ] Register each thread you will draft for (track_outreach.py register)
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
| Which video fits which post | Keyword-to-video lookups |
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
| `fetch_videos.py` | Newest uploads on the alliance YouTube channels, with date, views and description (default 180 days) | No |
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

#### 1d. Alliance videos (YouTube)

The alliance publishes its own videos now, and they are newer than the two
that used to close every reply. List both channels before scouting, so each
reply can carry the video that fits the post.

| Channel | What is on it |
|---------|---------------|
| `https://www.youtube.com/@MinmatarFleet/videos` | The official channel: town hall highlights, Rock Hoppin', skits, Shorts |
| `https://www.youtube.com/@FayeVaelent/videos` | Faye Vaelent's edits: the year in review, The Cope (a news parody of the big fights), brawl montages |

```bash
python scripts/fetch_videos.py --json
```

No credentials. It reads each channel's public feed: the newest 15 uploads
with date, view count, description, and whether the upload is a Short.
Channels live in `config.json` under `youtube.channels`. The feed stops at 15
per channel, so open the channel page when you want an older video.

Then refresh the **Video shelf** in the Current kit:

1. For every upload that is not on the shelf yet, read the title and the
   description and write down which kind of post it answers. You cannot watch
   it, so go by title, description, length and date. When those do not tell
   you what the video shows, leave it off and name it in section 1 for the
   recruiter to place.
2. When a new video does the same job as an older row, the new one takes the
   row. One town hall, one year in review, one newest-fight video.
3. Keep the shelf to about ten rows. It is what you will pick from, not an
   archive of the channels.
4. Leave off what a stranger cannot use: an ad for an event that is over,
   lore or roleplay series, anything unlisted. A video about a fight we lost
   is fine to keep when the title is a joke we would make ourselves.

**Proof closes (required stack):**

| Layer | Resource | When |
|-------|----------|------|
| **Always on r/evejobs and forums** | **One video from the shelf, picked for this post** (see "Pick the video for the post") | **Every r/evejobs and forum send.** Mining, MFA, no-PvP, WH redirect, named corp, saturated thread. Own block. Bring Fun Shit is the pick when nothing on the shelf fits. **Not on r/eve.** |
| **Also big fight** | Newest AAR in the Current kit | PvP/FW, caps, Rattini, WH→FW, “where’s the action,” on r/evejobs and forums. One AAR max unless they asked for capitals — then you may add the cap-feed AAR too. Skip it when the picked video is already about that same fight. Never a substitute for the video there. On r/eve, this AAR is the whole reply when the thread is about fights. |

Do not dump every video and AAR into every message. On r/evejobs and forums,
do not skip the video because an AAR is already in the reply. On r/eve, skip
the video stack. The reply is one content piece: an AAR, the warzone report,
the Amamake market report, or a fight video (see the r/eve section).

#### Current kit (update from pre-scout 1c and 1d)

Replace AAR rows when a new mega-fight AAR posts, and video rows when a newer
video does the same job. URLs also live in `config.json` (`proof_videos`,
`proof_aars`, `proof_pages`).

**Video shelf** (one per r/evejobs and forum reply; last refreshed 2026-11-14):

| Video | Published | URL | Pick it when the post… |
|-------|-----------|-----|------------------------|
| Minmatar Fleet Alliance YC128 In Review (Faye Vaelent, 5 min) | 2026-11-14 | `https://youtu.be/Vu7IXZd80bQ` | is thin or general, or asks what we actually do. The year in one video. |
| The Cope: The Battle of Amamake II (Faye Vaelent, 1.5 min) | 2026-11-07 | `https://youtu.be/ORIlXO7iw-8` | asks where the action is, or is a veteran coming back to shoot. The newest big fight. Part I is `https://youtu.be/8EPWdoXpu5s`. |
| Minmatar Fleet Town Hall #38 highlights (official, 16 min) | 2026-11-07 | `https://youtu.be/qZwMM5xm7c0` | asks how the alliance is run or whether it is active, wants a job (FC, capitals, industry, PI, freight, black ops), or is a corp looking for an alliance. It has census, tribes and the war plan. |
| The Cope: The Imperium declares war on LOWSEC (Faye Vaelent, 2 min) | 2026-11-01 | `https://youtu.be/FQf0IybswYU` | comes from nullsec or a bloc and doubts lowsec has fights at their scale. |
| Short: Minmatar tackles a DREADNOUGHT. Lasts two seconds. (official) | 2026-09-09 | `https://youtu.be/AUL2zM8Igrc` | is from a brand-new pilot afraid of being useless or of dying. |
| AT XXII Super Feeders (official, 4 min) | 2026-09-02 | `https://youtu.be/09-PtM6K3Xs` | wants laid-back people, jokes about their own killboard, or is done with sweaty groups. A skit, not footage. |
| Rock Hoppin' (official, Minmatar Extraction Company, 1 min) | 2026-07-31 | `https://youtu.be/XCApG7Pt6m4` | is about mining or industry: Extraction, MFA rock fleets, highsec bulwark miners, a corp-merge industry crew. |
| Minmatar Fleet Alliance brawls in Amamake (Faye Vaelent, 4 min) | 2026-07-12 | `https://youtu.be/6OZd594h2CM` | wants small gang and fleet brawls, shown plainly as footage. |
| The Cope: Dread Brawl in Dal (Faye Vaelent, 3 min) | 2026-02-23 | `https://youtu.be/8T6DGictq-g` | is about capitals or dreads. Stays until a newer capital video posts. |
| Bring Fun Shit (General) | older | `https://youtu.be/7-eGTtq9vWo` | fits nothing above. The fallback, never the default. |

**AARs and pages:**

| Kind | Title | URL | Use |
|------|-------|-----|-----|
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
  which is SOEXD. A shelf video always; optional WH-operator credibility. Add
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

Open the thread and read every reply. Each thread is one of three:

| State | What is on the thread | What you do |
|-------|-----------------------|-------------|
| **Ours** | A reply posted from this tool. On Reddit that is `u/BearThatCares` or `u/MinmatarFleet` (`reddit.scout_accounts` in `config.json`). On the forums it is BearThatCares. | Already replied. Section 2. No draft. |
| **Another recruiter** | A pitch from anyone else in the alliance: it names Minmatar Fleet, FL33T, an alliance corp, or `discord.gg/minmatar`. | Route the pilot anyway, then compare. See below. |
| **Open** | Neither. | Route and draft. |

A stranger saying “try the Amarr-Minmatar warzone / Amamake” is not a reply
from us. It takes a FL33T recruiter, a named alliance corp, or
`discord.gg/minmatar`.

A thread that `track_outreach.py` registered on an earlier run but that has
no reply from a scout account was never pasted. Treat it as open. Registering
it again returns the same code.

#### Another recruiter already replied

Recruiters pitch their own corp, and some paste the same Academy text under
every thread. One reply like that does not close the thread for the other
corps in the alliance. Route the pilot from the map as if nobody had
answered, then read the other reply against the seat you chose:

| Their reply | What you do |
|-------------|-------------|
| **Already the reply you would send.** It names the routed seat, or a seat that fits the pilot just as well, it answers what the pilot wrote, and it has a way in (the ad or Discord). | Leave it. Section 2, with the corp they pitched. No draft. |
| **The pilot fits a different corp.** They pitched Academy to a miner, their own small-gang corp to a brand-new pilot, the alliance in general to someone who needs one named seat. | Draft a second reply for the routed seat. Sections 3 and 4, marked `second reply`. |
| **Right corp, thin pitch.** | Do not pitch the same corp twice. Section 2, and say the pitch was thin so the recruiter can follow up by hand. |
| **The pilot already answered them.** | If they took it (joined Discord, said thanks, applied), the thread is done: section 2. If they turned something down, that is routing information. Do not pitch what they refused, and draft only when another seat still fits. |

Hold "already the reply you would send" to a real standard. A generic paste
with the wrong seat is not it, however polite. A recruiter who read the post
and named the right corp is, even when you would have worded it differently.

A second reply is still a normal reply, with these differences:

- Post it to the pilot, as a top-level comment or a new forum post. Not
  under the other recruiter's comment.
- Never correct the other recruiter or call their corp the wrong one. Say
  what this corp offers the pilot. One clause can say it is in the same
  alliance as the corp already pitched, so the pilot sees two doors into one
  house instead of two competing recruiters.
- Keep it to one or two sentences. The thread already has our name on it.
- Do not repeat a link their reply already carries, except Discord. If they
  linked Bring Fun Shit, pick a different video. The Discord link stays
  because it is tracked, and that is how this reply gets counted.
- Register it with `track_outreach.py` like any other reply.

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
- **Industry-primary:** MFA associate corps primary. Base in highsec bulwark systems, lowsec excursions when people want out. PvP corp is a side note only. Name **Minmatar Extraction Company** (and its Amo mining ad) when they want organized mining fleets; the MFA network on `discord.gg/minmatar` for general industry/PvE. Do not name a Discord person. Dual accounts (mining main + PvP alt) can split Extraction + the FW seat that matches the combat character. On forums, linking `my.minmatar.org/alliance/corporations/` works when dual-routing. Small industry **corps** seeking a null alliance home still get Extraction (fleet density / ore volume). The video is **Rock Hoppin'**.
- **Ex-FL33T returning:** if they already left Rattini and are not asking for dreads or a pile of characters, route **SLTAR** rather than sending them back to ARAT.
- **Caps / multi-box veterans:** ARAT. Unused capital + learning lowsec → ARAT (own the dread-feed joke). Close with the capital video from the shelf, then the cap-feed AAR from the Current kit (Ahbazon 700B until a newer cap brawl replaces it). **Straylight is not in the alliance** — never route or link there.
- **WH-only veterans, or jspace with no USTZ new/early-intermediate angle:** nameless FW redirect plus a fight video from the shelf and the newest kit AAR. Do not close that redirect with Rock Hoppin'. SOEXD is for USTZ new and early-intermediate pilots who still want a hole on the side.
- **Alliance positioning:** we are a **faction warfare** alliance. Daily content is FW and lowsec small gang. Do not pitch nullsec, sovereignty, null ratting, structure timers, or bloc null. If OP wants dedicated sov-null mining, pitch highsec bulwarks / Extraction instead — never "we have sov too." If OP wants dedicated nullbloc PAP/CRAB lifestyle with no industry-or-FW opening, leave unanswered rather than inventing a null pitch.
- **Proof closes above are for r/evejobs and the forums.** On r/eve, keep the seat in section 3, then send the content plug instead of the ad and video stack.

### Pick the video for the post

Every r/evejobs and forum reply carries **one** video, and it is the one that
answers what this pilot wrote. Do this after routing and before drafting,
once per prospect. It replaces the old habit of closing every reply with
Bring Fun Shit.

1. Reread the post for the one thing they are worried about or excited
   about: being new and useless, wanting fights tonight, a capital gathering
   dust, a barge, a bad killboard, whether anyone is actually in charge.
2. Go down the Video shelf and take the video that shows that thing. Between
   two that fit, the newer one wins.
3. Nothing fits: Bring Fun Shit.
4. Write the pick and three or four words of why next to the thread in
   section 3, so the recruiter can swap it before pasting.

How the shelf usually maps. This is a guide to reading posts, not a lookup.
A new upload can take any of these jobs once it is on the shelf.

| The post is about | Look for |
|-------------------|----------|
| Brand new, wants teaching, scared of losing ships | A short, funny clip where a newbro dies and nobody minds. Not a 16-minute town hall. |
| "Where's the action", returning veteran, wants big fights | The newest fight video: a Cope episode or a brawl montage. |
| Leaving nullsec or a bloc, unsure lowsec is worth it | A fight video with bloc names in the title. |
| Capitals, dreads, many characters | The newest capital video. |
| Mining, industry, PI, hauling | Rock Hoppin'. |
| Real life first, casual, no CTAs, self-described bad pilot | A skit. It shows the humor faster than a pitch can. |
| How the alliance is run, wants a role, a corp shopping for an alliance | The newest town hall highlights. |
| Thin post, "sell me", no clear ask | The newest year in review. |

Rules:

- **One video.** A second only when the post has two separate asks and the
  routing split them too: a mining main plus a PvP alt gets Rock Hoppin' and
  the PvP pick.
- **Routing first.** The video never changes the seat. A good video for the
  wrong corp is still the wrong video: Rock Hoppin' is Extraction's, so it
  does not go on a PvP reply.
- **Read the title the way the pilot will.** "The Death of Minmatar Fleet"
  is a good joke for someone who wants to feed capitals and a bad first
  impression for someone asking whether the alliance is stable.
- **Length is part of the fit.** A new player gets a Short or a two-minute
  clip. The town hall is for someone who asked a question it answers.
- **Same video on every reply in the run** means you matched to the shelf,
  not to the posts. Two similar posts can share a video. Seven cannot.
- **A second reply** (another recruiter got there first) does not reuse the
  video their reply linked.
- The pitch does not have to mention the video. A plain clause is fine when
  the video answers their question ("the last town hall has the numbers").
  Do not describe or sell it.

Where it goes: on r/evejobs it is a bullet in `Some links`. On the forums it
is a bare `https://youtu.be/...` URL on its own line so Discourse embeds it.
Use the `youtu.be` form for Shorts too. YouTube links are never tracked.

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
| **Forums** | The ad URL as bare text and `discord.gg/minmatar` as a tracked link in the last sentence. | Each proof URL on its own line so Discourse embeds it: the picked video, then one AAR. No bold YouTube URLs. No `Some links` list. |

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
  Never link an r/evejobs ad, Discord, or a video about the alliance (the
  year in review, a town hall, a skit, Rock Hoppin', Bring Fun Shit).
- Exactly one URL, on its own line, no label, no bullets. The URL is the
  comment. Do not skip it.
- Pick the piece that matches the thread:
  - Fights, faction warfare, "where's the action", returning to shoot: the
    newest kit AAR. Capitals: the cap-feed AAR.
  - The thread is about one specific fight and the shelf has a video of that
    fight (a Cope episode, a brawl): the video can be the one URL in place of
    the AAR. Only a video about the fight. Never one about us.
  - How the war is going, occupancy, a returning pilot asking what changed:
    the monthly warzone report.
  - Mining, market, ISK, industry, the station economy: the Amamake market
    report.
- Warzone and Amamake links use tracked hrefs. AARs and fight videos stay
  bare URLs.

```
[one or two sentences that answer the thread and point at the piece]

[one URL alone]
```

#### Before you present

Read every draft in the run back to back against the "Tells to catch" list
in `voice.md`. Two drafts that open the same way or share a phrase means one
gets rewritten. Then check the proof stack: every r/evejobs and forum draft
has one video, and you can say in a few words why that video for that post;
mining and industry drafts have Rock Hoppin'; PvP, FW, caps and redirects add
the newest kit AAR when the thread has room and the video is not already
that fight. r/eve drafts stay one or two sentences plus one URL. A second
reply does not contradict the first recruiter and does not repeat their
video.

### Tracked links

Discord and my.minmatar.org links carry a per-reply code so recruiters can see
which replies get clicked. Nothing else is tracked: corp ads, AARs, YouTube and
any other link stay exactly as they are.

1. After routing, register every thread you will draft for, second replies
   included:
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
onebox card. That is fine for the corp directory and warzone report. Videos
and AARs keep their bare URLs so they still embed.

Bots that unfurl a link (Discourse onebox, Reddit, Discord) are recorded but not
counted, so posting a reply does not count as a click.

### Present output

Four sections, in this order. Sections 1–3 are for reading. Section 4 is what a
recruiter copies. Do not put the pitch inside a markdown table.

#### 1. Overview of the results

Short prose: lookback window, how many player posts, how many already replied
(ours, and covered by another recruiter), how many still need a reply, how
many of those are second replies, how many true no-replies. Name the corp
seats used this run in one sentence. Flag a kit change here if one happened:
a new AAR, a video added to or dropped from the shelf, or a new upload you
could not place.

Then one or two sentences from `track_outreach.py stats --days 30`: replies per
surface, how many got any click, how many clicked Discord, and which seats or
openings drew clicks. Note it when tracking was skipped this run (no token).

#### 2. Overview of who we've already replied to

One line per thread. Title, who replied (Reddit username or forum username),
corp they pitched if they named one, link. No new draft. Ours first. Then the
threads another recruiter covered, each with a few words on why their reply
stands (right seat, pilot already said yes, right corp but thin).

#### 3. Overview of who we need to reply to

One line per thread that gets a draft. Title, seat (ticker plus corp name), why
that seat in a few words, the video picked and why, link. Mark a second reply
and say who got there first and what they pitched (`second reply: u/name
pitched Academy`). Industry redirects and nameless FW redirects belong here too.
True no-replies get their own short list under this section, not mixed into the
reply list.

#### 4. Copy-pastable replies

One block per thread that gets a draft, in the same order as section 3. Each block:

1. A heading the recruiter does not paste: title, seat, `r/evejobs`, `r/eve`, or `Forums`, tracking code, link to the thread, and `second reply after u/name` when another recruiter already posted.
2. A fenced code block they can copy whole.

**r/evejobs** (what actually gets sent):

- Pitch is one paragraph and contains no URLs.
- Blank line, then the line `Some links`, then a markdown bullet list.
- Each bullet is a markdown link whose visible text is the URL: `* [https://…](https://…)` . For my.minmatar.org pages the href is the tracked link: `* [https://my.minmatar.org/learning/](https://my.minmatar.org/go/<code>/learning)` .
- Discord is `* [discord.gg/minmatar](https://my.minmatar.org/go/<code>/discord)` (plain `http://discord.gg/minmatar` only when tracking was skipped).
- Do not name a Discord person in the pitch or the link list. Discord in the list is the contact.
- Brand-new teach-me Academy posts put `https://my.minmatar.org/learning/` first in the list and skip the AAR.
- Other Academy / PvP posts: ad, discord, the picked video, then one AAR when the kit says so.
- Mining / industry posts: the mining ad, Rock Hoppin', discord. Order can put discord first when the ask is a corp home rather than “how do I mine.”

**r/eve** (what actually gets sent):

- One or two sentences, no URLs inside them. Answer the thread. Do not name a corp.
- Blank line, then exactly one URL. No `Some links`, no bullets, no r/evejobs ad, no Discord, no video about the alliance.
- Fights and "where's the action": the newest kit AAR, bare. Capitals: the cap-feed AAR, bare.
- How the war is going: `[https://my.minmatar.org/warzone/](https://my.minmatar.org/go/<code>/warzone)`.
- Mining, market, or ISK: `[https://my.minmatar.org/amamake-market/](https://my.minmatar.org/go/<code>/amamake)`.
- Register the thread with `--surface eve`. An AAR stays a bare Reddit URL. A site report uses the tracked href.

**Forums** (bare URLs, so Discourse oneboxes):

- Pitch is one paragraph. The corp ad URL sits in the last sentence as bare text. `discord.gg/minmatar` sits there too as the one markdown link, `[discord.gg/minmatar](https://my.minmatar.org/go/<code>/discord)`. No other markdown links, no bold. Do not add an "ask for" name.
- Blank line, then each proof URL on its own line: the picked video, then one AAR when the kit says so.
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
| `reddit.scout_accounts` | Accounts this tool's replies are posted from (`BearThatCares`, `MinmatarFleet`). A reply from one of these is ours; any other alliance recruiter is not |
| `youtube.channels` | Alliance YouTube channels for `fetch_videos.py` (`@MinmatarFleet`, `@FayeVaelent`) |
| `reddit.subreddits` | Subreddits for raw `/new` fetch |
| `forums.recruitment_center_category` | Forum category slug |
| `discord_invite` | For outreach closers (skill only) |
| `tracked_links.targets` | Link targets for `my.minmatar.org/go/<code>/<target>`; must match `frontend/app/src/json/scout-links.json` |
| `proof_videos.shelf` | The Video shelf: one is picked per r/evejobs and forum send; refresh it when the channels post |
| `proof_videos.fallback` | Bring Fun Shit — only when nothing on the shelf fits |
| `proof_aars` | Current billion-ISK AARs (newest first); rotate when a new one posts |
| `proof_pages` | Warzone report, Amamake market report, corp directory, freight history, optional siege pages |

## Additional resources

- Past outreach learnings (add as you go): [examples.md](examples.md)
- Data scripts: [scripts/](scripts/)
- Setup: [README.md](README.md)
