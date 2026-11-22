---
name: backend-review
description: >-
  Standard code review for backend changes (backend/: Django apps, Ninja
  endpoints, models and migrations, Celery tasks, management commands; and
  bot/). Run it on the final diff before opening or updating a pull request,
  and paste its Result block into the pull request's "Backend review" section.
  Use when asked to review backend code, review a PR's backend changes, or
  fill in the PR template's backend review.
---

# Backend review

The review every pull request that touches `backend/` or `bot/` gets before it is opened. It checks the diff
against the backend rules, then runs the checks CI runs. The pull request template
(`.github/pull_request_template.md`) asks for its Result block, and `scripts/check_pull_request.py` fails the
pull request without it.

The rules live in `.claude/rules/` and the architecture docs under `docs/architecture/`. This skill is the
checklist; those documents are the rules. When they disagree, the documents win, and fix this skill.

## 1. Scope

```bash
git fetch origin main
git diff --stat origin/main...HEAD -- backend bot
git diff origin/main...HEAD -- backend bot
```

Review the **final** diff of the branch, not one commit. Read the whole function, not just the changed lines, and
find its callers (`grep -rn "<name>" backend`).

## 2. Correctness

Find bugs before style:

- Edge cases: `None`, empty querysets, a character with no corporation, a deleted Discord user, a soft-deleted
  row, a fleet with no members, duplicate ESI or zKill rows, alts of the same person counted twice.
- Time: aware datetimes only; EVE time is UTC; date boundaries (week opens, month rollups) are tested.
- Concurrency: two workers or two clicks running the same code; `get_or_create` races; a task retried after
  half its work. Use the task options (`exclusive=`, `cooldown=`) and transactions, not hand-rolled locks.
- Errors: no bare `except`; failures that matter reach Sentry; a failure in one item of a loop doesn't silently
  drop the rest.

## 3. Access and data exposure

- Every endpoint authenticates and checks access the same way its neighbours do (permission, pilot feature or
  per-object right), and the test covers the refused case.
- Responses leak nothing the viewer may not see: hidden rosters, private fleets, intel, other pilots' alts or
  ESI data, reviewer notes. Check every new field against who can call the endpoint.
- No raw SQL built from input, no secrets or tokens in logs, no user-supplied URLs fetched without a host check.

## 4. Project rules

Check the diff against each rule that matches the files it touches:

| Rule | What to check |
| --- | --- |
| `.claude/rules/one-file-per-endpoint.md` | One method + path per module in endpoints packages |
| `.claude/rules/celery-tasks.md` | `AppTask` only, no `queue=`, routing in `backend/app/queues.py`, fast-lane justification, no self-requeue |
| `.claude/rules/soft-delete.md` | `MinmatarSoftDeleteModel`, default manager in product code, `get_or_create_active` |
| `.claude/rules/django-esi-client.md` | `results()` for paginated ESI, the wrapper in `backend/eveonline/client.py` |
| `.claude/rules/market-pricing.md` | The right price source for market, buyback and industry code |
| `.claude/rules/api-types.md` | Typed Ninja response schemas; `openapi.json` and `api.d.ts` regenerated |
| `.claude/rules/desktop-release.md` | Desktop-facing endpoints change additively; contract files regenerated on purpose |
| `.claude/rules/testing.md` | Tests use test settings, never reach the network, migration tests tagged |

## 5. Migrations and deploys

- Migrations work with the code that is already running (`docs/architecture/deploys.md`): add in one release,
  drop or rename in a later one.
- Data migrations are reversible or say why not, and run in reasonable time on production-sized tables.
- New filters and joins on large tables have an index.
- After a rebase, migration numbers don't collide with `main`.

## 6. Production scale

- No N+1 queries in loops or serializers: `select_related`/`prefetch_related`, or one aggregate query.
- Heavy rollups are computed by Celery and read from the cache (`docs/architecture/cached-aggregates.md`), not
  computed in a request. Dev data hides production cost: estimate row counts.
- Lists are paginated or bounded.
- External calls respect rate limits (ESI error budget, Discord: post once, don't edit in loops).

## 7. Tests

- New behaviour has tests, including the refused-access case and the empty case; a fixed bug has a test that
  failed before the fix.
- Tests don't depend on order or wall-clock time; they seed or mock what they need instead of reaching ESI,
  zKill or Discord (`backend/app/test_network_guard.py` blocks it).

## 8. Run the checks

From `backend/`:

```bash
pipenv run python manage.py test --settings=app.settings_test --parallel auto --exclude-tag migration
pipenv run black --check .
pipenv run flake8 .
pipenv run pylint <changed apps>
```

Run only the affected apps while iterating, then the full suite once before the result. When a migration changed,
also run `--tag migration`. When an endpoint or schema changed, regenerate the OpenAPI document and the website
types (`.claude/rules/api-types.md`) and commit them. For `bot/`: `pipenv run python -m unittest discover -s tests
-t .` and `flake8 .` from `bot/`.

## 9. Fix, then report

Fix every finding you can. Anything left open is listed with the reason. Then write the result for the pull
request's "Backend review" section, in this shape:

```text
Backend review (backend-review skill) on <short sha>:
- Fixed: <one line per fixed finding, or "nothing found">
- Open: <one line per finding left, with why, or "none">
- Checks: tests passed (<apps or "full suite">), black/flake8/pylint clean
- Migrations / schema: <"none", or what changed and that it was regenerated>
```

A review with open correctness or access findings, or failing checks, is not ready to merge: say so in the result
rather than ticking the box.
