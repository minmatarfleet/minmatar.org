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
- [ ] Scout: find player LFC posts (past 7 days) — browse, search, or optional script
- [ ] Read each thread; decide responded vs open
- [ ] Route each open prospect to one primary corp (from pre-scout bios)
- [ ] Draft outreach using voice rules below (+ any entries in examples.md)
- [ ] Present two tables
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
Administrative Atrocities, etc.). **Only route to corps present in the API**
and with a recent ad — corps leave the alliance (e.g. Straylight is gone).

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

**Exclude** when:

- A corp or alliance is recruiting members (the recruiter posted, not the pilot)
- The pilot explicitly does not want a corporation
- The post is outside the lookback window
- It is your own alliance recruitment post (e.g. `Recruiting corporations who want help growing!` from `u/MinmatarFleet`)
- WH-only seekers, if they are a poor fit for your FW/lowsec corps (note in skipped list)
- Sov-null-only seekers (dedicated nullbloc, null ratting, structure defense, ESS
  in sov space) — poor fit; note in skipped list, do not pitch nullsec

When unsure, open the thread and read it.

### Detect "Responded"

Open the thread. Mark **Y** if your alliance already reached out — a recruiter
reply, a corp pitch mentioning Minmatar Fleet / FL33T / `discord.gg/minmatar`, or
any clear prior outreach from your side.

**Already responded → separate table. Do not draft new outreach.**

### Route to the right corp

**Source of truth:** pre-scout data only. Read corporation profiles from the API
(`introduction`, `biography`, `timezones`, `requirements`) and match prospects
against recent `u/MinmatarFleet` ads. Corps change over time.

This is your judgment call. Read the pilot's post, read the corp bios, pick one
primary corp. Skip or note poor fits (e.g. WH-only seekers) in a short bullet list.

**Principles** (apply using current `requirements` fields from the API):

- Check each corp's `requirements` before routing. A corp that expects active
  fleet participation or leadership roles is a poor fit for casual or patchy
  playtime unless the pilot explicitly wants that commitment.
- Industry-primary pilots belong in **Minmatar Fleet Associates (MFA)** associate
  corps, not FW alliance corps. MFA lives in **highsec bulwark systems** with
  **lowsec excursions** — pitch that, not FW daily life. Mention a PvP corp only
  as an optional side path, not the primary pitch.

One primary corp per prospect. Optional one-liner for a graduate path or
bigger/smaller corp in the same alliance — name only, no ad link. Use
`(same alliance)` when naming a secondary corp (e.g. `administrative atrocities
(same alliance)`).

**FL33T routing notes** (verify against API each scout; corps rename):

- **New EU pilots:** Minmatar Fleet Academy first, graduate path to
  **Administrative Atrocities** (EUTZ, more experienced). Do not default new EU
  pilots to Rattini. Administrative Atrocities was formerly DHDR — always use
  the name from the corporations API, not stale external tickers.
- **Industry-primary:** MFA associate corps primary. Base in highsec bulwark
  systems, lowsec excursions when people want out. PvP corp is a side note only.
- **Blops/caps/lowsec bloodshed:** Rattini Tribe (all TZ, escalates into cap
  fights) or **Administrative Atrocities** (tight EUTZ skirmish crew). Match TZ
  and vibe (big pond vs small roster). **Straylight is not in the alliance** —
  never route or link there.
- **Alliance positioning:** we are a **faction warfare** alliance. Daily content
  is FW and lowsec small gang. Do not pitch nullsec, sovereignty, null ratting,
  structure timers, or bloc null. If OP wants dedicated sov-null, skip or note poor
  fit — do not redirect with "we have sov too" or similar.

### Draft outreach

Read [examples.md](examples.md) for past learnings if any exist. Every recommended
message is **one short paragraph** — punchy, readable on a phone, no line breaks.

#### Shape (always)

**One paragraph. 2–4 sentences max.** Weave their detail, name one primary corp,
what it does, then ad link and/or discord inline at the end. No bullet lists, no
second paragraph, no wall of text.

```
[hook: their words, a fear, or what the corp does — first sentence grabs attention]

[corp + one concrete detail tied to their post + optional graduate/alt corp in passing]

[ad link and/or discord.gg/minmatar woven into the last sentence]
```

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

**Self-check:** each message should be scannable in under 5 seconds.

**Voice rules:**

- Sound human, not marketing. No em dashes. No AI filler.
- Do not open with "Hey —" or "I saw your post".
- **Weave, don't dump.** Work one or two OP details into the pitch naturally.
  Vary where they land: sometimes lead with corp, sometimes with their situation,
  sometimes with a direct reply to their question. Never open every message with
  the same comma-chain mirror (`holland, eu nights, new but wanting pvp?`).
- **No question-form mirroring.** Do not restate their post as a rhetorical
  question (`industry, mining ops, pve, fw sounds interesting?`).
- **No salesy fit language.** Avoid "probably the move", "good fit", "worth a
  look" stacked together, or listing `you want X, Y, Z`. Describe the corp; let
  them decide.
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
- **One paragraph only.** Reddit and forums use the same shape. Link + discord
  inline; skip discord when the ad link is enough.
- Keep motivational lines only when OP is about to quit EVE (still one paragraph).

### Present output

## Already responded (no further outreach)

| Title | Responded | Type | Link | Notes |
|-------|-----------|------|------|-------|

## Open prospects

| Title | Corp fit | Responded | Type | Link | Recommended message |
|-------|----------|-----------|------|------|---------------------|

Put recommended messages in the table as a **single paragraph** (no line breaks).

Below the tables, optionally list:

- Corporation roster + latest reddit ad URLs (from pre-scout output)
- Skipped posts (WH-only, poor fit) in one short bullet list

## Configuration

`config.json` tells the optional collector **where to fetch** — API URL, subreddits,
forum category, `u/MinmatarFleet`. It does not encode triage rules, response
markers, or routing. Those live in this skill.

| Field | Purpose |
|-------|---------|
| `api_base_url` | Corporation API base |
| `reddit.recruitment_account` | Recruitment Reddit user (`MinmatarFleet`) |
| `reddit.subreddits` | Subreddits for raw `/new` fetch |
| `forums.recruitment_center_category` | Forum category slug |
| `discord_invite` | For outreach closers (skill only) |

## Additional resources

- Past outreach learnings (add as you go): [examples.md](examples.md)
- Data scripts: [scripts/](scripts/)
- Setup: [README.md](README.md)
