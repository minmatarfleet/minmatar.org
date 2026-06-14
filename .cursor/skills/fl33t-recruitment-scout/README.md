# EVE Alliance Recruitment Scout

A Cursor Agent Skill for finding pilots who are **looking for a corporation**,
routing them to the right corp, and drafting short, human outreach replies.

**The skill is the product.** `SKILL.md` and `examples.md` define the workflow and
judgment. They improve over time as you add real outreach examples and refine
routing principles.

`scripts/` provides **single-purpose fetchers** the agent can run à la carte —
not a monolithic pipeline.

Built around [Minmatar Fleet Alliance](https://my.minmatar.org/) as the reference
implementation.

## What it does

**Agent (primary):**

1. Pre-scout: corp profiles from `api.minmatar.org`, recent `u/MinmatarFleet` ads
2. Scout: find LFC posts on Reddit and EVE Forums
3. Judge responded vs open, route to corp, draft outreach

**Scripts (optional):** run only the fetchers you need. No keyword filtering.

## Scripts

| Script | Purpose | OAuth? |
|--------|---------|--------|
| `fetch_corporations.py` | Corp profiles from public API | No |
| `fetch_recruitment_ads.py` | `u/MinmatarFleet` ads (default 30d) | Yes |
| `fetch_reddit.py` | Raw subreddit `/new` (default 7d) | Yes |
| `fetch_forums.py` | Forum recruitment-center latest (default 7d) | No |
| `match_corp_ads.py` | Map ad URLs → corp names | No |

Shared helpers live in `scout_lib.py` (not invoked directly).

## Quick start

```bash
cd .cursor/skills/fl33t-recruitment-scout
pip install -r requirements.txt

# Load Reddit credentials from backend/.env (local only — never commit)
set -a && source ../../../backend/.env && set +a

python scripts/fetch_corporations.py --json
python scripts/fetch_recruitment_ads.py --days 30 --json
python scripts/fetch_reddit.py --days 7 --json
python scripts/fetch_forums.py --days 7 --json
```

### Recruitment Reddit account

Corp recruitment ads are posted by **`u/MinmatarFleet`** on `r/evejobs`.

Browse manually: https://www.reddit.com/user/MinmatarFleet/submitted/

## Configuration

`config.json` tells the fetchers where to look. Triage and routing live in the skill.

| Field | Purpose |
|-------|---------|
| `api_base_url` | Base URL for corporation API |
| `corporation_types` | Corp groups to load (`alliance`, `associate`, etc.) |
| `reddit.recruitment_account` | Recruitment Reddit user (`MinmatarFleet`) |
| `reddit.subreddits` | Subreddits for raw `/new` fetch |
| `forums.recruitment_center_category` | Forum category slug |
| `discord_invite` | Invite link for outreach closers (skill only) |

### Reddit OAuth

Load from **`backend/.env`** before running Reddit scripts:

- `REDDIT_CLIENT_ID`
- `REDDIT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`

```bash
# from repo root, or use ../../../backend/.env when cwd is this skill folder
set -a && source backend/.env && set +a
python scripts/fetch_reddit.py --json
```

`fetch_corporations.py` and `fetch_forums.py` work without OAuth.

## Cursor usage

```
Run the alliance recruitment scout for the past 7 days
```

The agent follows `SKILL.md` and runs whichever scripts (or manual fetches) fit the task.

## License

Publish under your open source license of choice.
