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
plus [examples.md](examples.md): workflow, judgment, voice. A model gets better at
recruitment scouting as those improve, not as Python heuristics accumulate.

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
- [ ] Draft outreach using voice rules + examples.md
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

Update [examples.md](examples.md) when real outreach teaches you something new.
That is the feedback loop.

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
corp ads on `r/evejobs` (Rattini, Soltech, Dark Tribe, Academy, Straylight,
Administrative Atrocities, etc.).

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
- WH-only seekers, if they are a poor fit for your null/low/fw corps (note in skipped list)

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
- Industry-primary pilots may belong in MFA associate corps; mention PvP corps
  only as an optional side path, not the primary pitch.

One primary corp per prospect. Optional one-liner for a graduate path or
bigger/smaller corp in the same alliance — name only, no ad link. Use
`(same alliance)` when naming a secondary corp (e.g. `administrative atrocities
(same alliance)`).

**FL33T routing notes** (verify against API each scout; corps rename):

- **New EU pilots:** Minmatar Fleet Academy first, graduate path to
  **Administrative Atrocities** (EUTZ, more experienced). Do not default new EU
  pilots to Rattini. Administrative Atrocities was formerly DHDR — always use
  the name from the corporations API, not stale external tickers.
- **Industry-primary:** MFA associate corps primary; PvP corp is a side note.
- **Alliance positioning:** daily PvP content is lowsec/fw. The alliance **does
  hold sovereignty** for krabbing and some fights — never say "we're not null" or
  "mostly lowsec fw not sov null" as if we have no sov.

### Draft outreach

Read [examples.md](examples.md) before writing messages. **Read several examples
and vary structure** — do not reuse the same opening trick across messages in one
scout run.

**Shape (flexible, not a fixed order):**

```
[weave 1-2 details from their post into the pitch — placement varies]

[one primary corp, plain language — describe what they do, not "good fit" sales]

[optional: graduate path or alt corp (same alliance), no link]

[ad link if reddit + clear single fit]

[{discord_invite} + casual closer]
```

**Voice rules:**

- Sound human, not marketing. No em dashes. No AI filler.
- Do not open with "Hey —" or "I saw your post".
- **Weave, don't dump.** Work one or two OP details into the pitch naturally.
  Vary where they land: sometimes lead with corp, sometimes with their situation,
  sometimes with a direct reply to their question. Never open every message with
  the same comma-chain mirror (`holland, eu nights, new but wanting pvp?`).
- **No question-form mirroring.** Do not restate their post as a rhetorical
  question (`industry, mining ops, pve, null sounds interesting?`).
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
- Discord: plain invite with casual closer (`if you wanna yap`, `hit us up`, etc.)
- **Forums**: usually no reddit ad links; one tight block with newlines.
- **Reddit**: 1 ad link for clear single fit; 2 links only when offering small
  corp vs bigger corp.
- Keep motivational lines only when OP is about to quit EVE.

### Present output

## Already responded (no further outreach)

| Title | Responded | Type | Link | Notes |
|-------|-----------|------|------|-------|

## Open prospects

| Title | Corp fit | Responded | Type | Link | Recommended message |
|-------|----------|-----------|------|------|---------------------|

Put recommended messages in the table cell with `<br><br>` between paragraphs
(for readability in the UI).

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

- Outreach examples (primary feedback loop): [examples.md](examples.md)
- Data scripts: [scripts/](scripts/)
- Setup: [README.md](README.md)
