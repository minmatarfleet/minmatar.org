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
plus [examples.md](examples.md): workflow, judgment, voice. `examples.md` starts
empty — add real outreach there as learnings accumulate.

`scripts/` holds **optional single-purpose fetchers** the agent can mix and match.
They do not route corps or draft messages. You can also hit endpoints and browse
directly — scripts are convenience for Reddit OAuth and pagination.

Configurable for any alliance. The reference implementation uses
[Minmatar Fleet Alliance](https://my.minmatar.org/) and `api.minmatar.org`.

## Quick start

**Agent workflow (primary):** follow the two phases below. Read corp bios, scan
sources, judge fit, draft outreach per examples.

**Optional fetchers** (run only what you need):

```bash
cd .cursor/skills/fl33t-recruitment-scout
pip install -r requirements.txt

# Reddit OAuth — load from backend/.env (do not commit these values)
set -a && source ../../../backend/.env && set +a

python scripts/fetch_corporations.py --json
python scripts/fetch_recruitment_ads.py --days 30 --json
python scripts/fetch_proof_media.py --days 45 --json
python scripts/fetch_reddit.py --days 7 --json
python scripts/fetch_forums.py --days 7 --json
```

Reddit credentials (`REDDIT_CLIENT_ID`, `REDDIT_SECRET`, `REDDIT_USERNAME`,
`REDDIT_PASSWORD`) live in `backend/.env`. Needed for `u/MinmatarFleet` ad
history and reliable Reddit comment reads. Corporation data loads from the public
API without them.

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
- [ ] Scout: find player LFC posts (past 7 days) — browse, search, or optional script
- [ ] Read each thread; decide responded vs open
- [ ] Route each open prospect to one primary corp (from pre-scout bios)
- [ ] Draft outreach using voice rules below (+ any entries in examples.md)
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

Update [examples.md](examples.md) after sending outreach that worked — that is the
feedback loop. Do not pre-fill templates.

### Data scripts (pick what you need)

| Script | Purpose | Needs Reddit OAuth? |
|--------|---------|---------------------|
| `fetch_corporations.py` | Corp bios, timezones, requirements from API | No |
| `fetch_recruitment_ads.py` | `u/MinmatarFleet` submissions (default 30 days) | Yes |
| `fetch_proof_media.py` | `u/BearThatCares` AARs / capital videos (default 45 days) | Yes |
| `fetch_reddit.py` | Raw `/new` from `r/evejobs`, `r/eve` (default 7 days) | Yes |
| `fetch_forums.py` | Recruitment-center latest topics (default 7 days) | No |
| `match_corp_ads.py` | Map ad URLs to corp names (optional convenience) | No |

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

Gather fresh **battle reports and capital / big-fight videos** to weave into
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
| **Always** | **Bring Fun Shit** | `https://youtu.be/7-eGTtq9vWo` | **Every send.** Mining, MFA, no-PvP, WH redirect, named corp, saturated thread. Own block. |
| **Also mining / industry** | **Rock Hoppin'** (Extraction Company) | `https://youtu.be/XCApG7Pt6m4` | Extraction, MFA rock fleets, highsec bulwark miners, corp-merge industry. **In addition to** Bring Fun Shit, not instead of it. Own block after BFS. |
| **Also big fight** | Newest AAR in the Current kit | see table | PvP/FW, caps, Rattini, WH→FW, “where’s the action.” One AAR max unless they asked for capitals — then you may add the cap-feed AAR too. Never a substitute for Bring Fun Shit. |

Do not dump every AAR into every message. Do not skip Bring Fun Shit because an
AAR or Rock Hoppin' is already in the reply.

#### Current kit (update from pre-scout 1c)

Replace rows when a new mega-fight AAR posts. URLs also live in `config.json`
(`proof_videos`, `proof_aars`, `proof_pages`).

| Kind | Title | URL | Use |
|------|-------|-----|-----|
| Video | Bring Fun Shit | `https://youtu.be/7-eGTtq9vWo` | Every send |
| Video | Rock Hoppin' | `https://youtu.be/XCApG7Pt6m4` | Mining/industry extra |
| AAR | 200B down in Dal (19 Sep YC128) | `https://www.reddit.com/r/Eve/comments/1wkwldz/aar_200b_down_in_dal/` | Default extra AAR (newest big fight) |
| AAR | 700B down in Ahbazon (1 Aug YC128) | `https://www.reddit.com/r/Eve/comments/1vcyik3/aar_700b_down_in_ahbazon/` | Caps / Rattini / dread-feed hook |
| Site | Monthly Warzone Report | `https://my.minmatar.org/warzone/` | Forums onebox / casual-null / action-location threads |
| Site | Corporation directory | `https://my.minmatar.org/alliance/corporations/` | Dual-route, self-serve bios |
| Site | Freight contracts history | `https://my.minmatar.org/market/freight/contracts/history/` | Hauler learning PvP (side proof, not MFA routing) |
| Site | Auga siege (YC128) | `https://my.minmatar.org/alliance/campaigns/auga-yc128/` | Optional older siege page; prefer Kamela AAR + warzone report when both fit |

### Phase 2: Scout (prospects)

Find posts from the **past 7 days** (or user-specified window) where a **player**
is looking for a corporation — not where a corp is recruiting.

**Sources:**

| Source | How |
|--------|-----|
| r/evejobs | `/new`, or search however you think will surface LFC posts |
| r/eve | Same; some pilots post outside evejobs |
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
  the newest kit AAR when the thread can take a second proof beat. Do not force
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
- **Industry-primary:** MFA associate corps primary. Base in highsec bulwark systems, lowsec excursions when people want out. PvP corp is a side note only. Name **Minmatar Extraction Company** (and its Amo mining ad) when they want organized mining fleets; MFA network + **Keldor00** on Discord for general industry/PvE. Dual accounts (mining main + PvP alt) can split Extraction + the FW seat that matches the combat character. On forums, linking `my.minmatar.org/alliance/corporations/` works when dual-routing. Small industry **corps** seeking a null alliance home still get Extraction (fleet density / ore volume). Close with **Bring Fun Shit then Rock Hoppin'** (two blocks).
- **Ex-FL33T returning:** if they already left Rattini and are not asking for dreads or a pile of characters, route **SLTAR** rather than sending them back to ARAT.
- **Caps / multi-box veterans:** ARAT. Unused capital + learning lowsec → ARAT (own the dread-feed joke). Close with Bring Fun Shit, then the cap-feed AAR from the Current kit (Ahbazon 700B until a newer cap brawl replaces it). **Straylight is not in the alliance** — never route or link there.
- **WH-only veterans, or jspace with no USTZ new/early-intermediate hook:** nameless FW redirect plus Bring Fun Shit and the newest kit AAR. Do not close that redirect with Rock Hoppin'. SOEXD is for USTZ new and early-intermediate pilots who still want a hole on the side.
- **Alliance positioning:** we are a **faction warfare** alliance. Daily content is FW and lowsec small gang. Do not pitch nullsec, sovereignty, null ratting, structure timers, or bloc null. If OP wants dedicated sov-null mining, pitch highsec bulwarks / Extraction instead — never "we have sov too." If OP wants dedicated nullbloc PAP/CRAB lifestyle with no industry-or-FW opening, leave unanswered rather than inventing a null pitch.

### Draft outreach

Read [examples.md](examples.md) for past learnings if any exist. Every recommended
**pitch** is **one short paragraph** — punchy, readable on a phone, no line breaks
inside that block. Proof video and forum oneboxes are **separate send blocks**,
never glued onto the pitch sentence.

#### Shape (always)

**One pitch paragraph. 2–4 sentences max.** Weave their detail, name one primary
corp, what it does, then ad link and/or discord inline at the end of that
paragraph only. No bullet lists, no wall of text.

```
[hook: their words, a fear, or what the corp does — first sentence grabs attention]

[corp + one concrete detail tied to their post + optional graduate/alt corp in passing]

[ad link and/or discord.gg/minmatar woven into the last sentence of the pitch]
```

**Send-shape (required — do not collapse into the pitch):**

| Surface | After the pitch paragraph |
|---------|---------------------------|
| **Reddit** | Pitch has no URLs. Blank line, then `Some links`, then a markdown bullet list. See section 4. |
| **Forums** | Pitch keeps the ad URL and `discord.gg/minmatar` as bare text in the last sentence. Then each proof URL on its own line so Discourse embeds it (Bring Fun Shit, Rock Hoppin' when mining, one AAR). Do not bold YouTube URLs. Do not use the Reddit `Some links` list. |

#### Variety (mandatory per scout run)

Draft all messages, compare side by side. Same rhythm = rewrite. Vary **how the
paragraph opens**, not how many paragraphs there are:

| Opening | First sentence… |
|---------|-----------------|
| Corp-first | What the corp does |
| OP-first | Their situation in plain words |
| Direct answer | Answers their question |
| Blunt | Ultra-tight when thread is saturated |
| Negative `tracks` | Only when OP vented |
| Contrast | "not sure X is wrong but…" |

Do not repeat the same opening mode or the same first three words across messages
in one run. Rotate how link/discord land (end of sentence, after corp name, etc.).

**Self-check:** each message should be scannable in under 5 seconds. **Every**
draft includes Bring Fun Shit. Mining/industry also includes Rock Hoppin'.
PvP/FW/caps/redirects also include the newest kit AAR when the thread has room.

**Voice rules:**

- Sound human, not marketing. No em dashes. No AI filler.
- Do not open with "Hey —" or "I saw your post".
- **Weave, don't dump.** Work one or two OP details into the pitch naturally.
  Vary where they land: sometimes lead with corp, sometimes with their situation,
  sometimes with a direct reply to their question. Never open every message with
  the same comma-chain mirror (`holland, eu nights, new but wanting pvp?`).
- **No question-form mirroring.** Do not restate their post as a rhetorical
  question (`industry, mining ops, pve, fw sounds interesting?`).
- **No salesy fit language.** Avoid "probably the move", "good fit", "probably
  the best fit", "worth a look" stacked together, or listing `you want X, Y, Z`.
  Describe the corp; let them decide.
- **`tracks` is for negatives only.** Valid: `goons feeling like a number tracks`.
  Invalid: `sons of bane taking care of people tracks`. Positive nostalgia gets
  a plain statement (`hard to find another sons of bane since winter co days`).
- One primary corp. Alliance mention is a footnote, not a second pitch.
- Stats only when they kill a stated fear (e.g. member count answers "not a 3
  person discord").
- No zkill links, no competitor comparisons, no brochure bullet lists.
- **No nullsec pitch.** Never mention sovereignty, null ratting, null deployment,
  or "we have sov too" in outreach. We are FW/lowsec; sov-null seekers get skipped
  or an honest FW pitch only if their ask fits.
- **One paragraph only** for the corp pitch. Reddit and forums use the same shape
  for that block. Link + discord inline in the pitch; skip discord when the ad
  link is enough. **Bring Fun Shit is required on every send**, own block (see
  send-shape). Rock Hoppin' is extra for mining/industry, never a BFS substitute.
  Add one Current-kit AAR for PvP/caps/redirects as they land; do not paste proof
  URLs into the pitch paragraph.
- **Forums Reddit ads:** prefer `/r/evejobs/s/` shortlinks so Discourse oneboxes
  as `Reddit`. Full reddit.com comment URLs also onebox as `Reddit`.
- **MFA Discord contact:** `ask for Keldor00` (handle, not the older `Keldor`
  shorthand).
- Keep motivational lines only when OP is about to quit EVE (still one paragraph).

### Present output

Four sections, in this order. Sections 1–3 are for reading. Section 4 is what a
recruiter copies. Do not put the pitch inside a markdown table.

#### 1. Overview of the results

Short prose: lookback window, how many player posts, how many already replied,
how many still need a reply, how many true no-replies. Name the corp seats used
this run in one sentence. Flag a kit change (new AAR) here if one happened.

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

1. A heading the recruiter does not paste: title, seat, `Reddit` or `Forums`, link to the thread.
2. A fenced code block they can copy whole.

**Reddit** (what actually gets sent):

- Pitch is one paragraph and contains no URLs.
- Blank line, then the line `Some links`, then a markdown bullet list.
- Each bullet is a markdown link whose visible text is the URL: `* [https://…](https://…)` .
- Discord is `* [discord.gg/minmatar](http://discord.gg/minmatar)` .
- Do not write `ask for Keldor00` in the pitch. Discord in the list is the contact.
- Brand-new teach-me Academy posts put `https://my.minmatar.org/learning/` first in the list and skip the AAR.
- Other Academy / PvP posts: ad, discord, Bring Fun Shit, then one AAR when the kit says so.
- Mining / industry posts: Bring Fun Shit, the mining ad, Rock Hoppin', discord. Order can put discord first when the ask is a corp home rather than “how do I mine.”

**Forums** (bare URLs, so Discourse oneboxes):

- Pitch is one paragraph. The corp ad URL and `discord.gg/minmatar` sit in the last sentence as bare text. No markdown links, no bold.
- Blank line, then each proof URL on its own line: Bring Fun Shit, Rock Hoppin' when mining, then one AAR when the kit says so.
- Named corp with no ad: bare `discord.gg/minmatar` in the pitch, then `https://my.minmatar.org/alliance/corporations/` on its own line before the videos.
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
| `proof_videos.always` | Bring Fun Shit — required on every send |
| `proof_videos.mining` | Rock Hoppin' — extra close for mining/industry |
| `proof_aars` | Current billion-ISK AARs (newest first); rotate when a new one posts |
| `proof_pages` | Warzone report, corp directory, freight history, optional siege pages |

## Additional resources

- Past outreach learnings (add as you go): [examples.md](examples.md)
- Data scripts: [scripts/](scripts/)
- Setup: [README.md](README.md)
