# Running Tests

`python3 scripts/ci_local.py` (repo root) runs the CI checks this branch's changes need: backend lint and tests,
bot, frontend, desktop, agent config. The agent hooks run it before every `git push` and pull request
(`docs/agent-ci-hooks.md`). Use the commands below to run a narrower set while you work.

Use Django's test runner with the test settings (SQLite, no external DB):

```bash
pipenv run python manage.py test --settings=app.settings_test
```

Run from the **backend** directory (`/root/minmatar.org/backend` or project's `backend/`).

- To run a specific app: `pipenv run python manage.py test eveonline --settings=app.settings_test`
- To run a specific test class or method: `pipenv run python manage.py test eveonline.tests.test_models.EvePlayerTestCase --settings=app.settings_test`

Do **not** use `python manage.py test` without `--settings=app.settings_test` unless the environment is configured for a test database (e.g. CI with DB create permissions).

## Speed and isolation

- Add `--parallel auto` to run across all cores (CI does this). Add `--keepdb` with `TEST_DB_NAME=.test-db/test_db.sqlite3` to reuse the migrated schema between runs.
- The test settings block all non-loopback network access (`app/test_network_guard.py`). A test that reaches ESI, zKill or Discord fails with `NetworkAccessBlocked`. Seed the eveuniverse rows it needs, mock the client, or gate the production call with `live_esi_allowed()`. Set `ALLOW_NETWORK_IN_TESTS=True` only for a deliberate live run.

## Migration tests

A test that drives `MigrationExecutor` re-renders the whole migration graph and takes seconds. Decorate its class with `@tag("migration")` (`app/tests/test_test_discovery.py` fails otherwise). CI runs these in their own job, and on pull requests only when the PR changes a migration. Run them locally with `--tag migration`.

## CI test database

CI restores the newest cached migrated DB and `--keepdb` applies only new migrations. `backend/ci_test_db.py` discards the cached DB when a migration it holds was renamed or edited, so renumbering a migration after a rebase is safe.
