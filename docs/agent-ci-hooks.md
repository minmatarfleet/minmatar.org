# Local CI and agent hooks

CI runs every check on every pull request, which is slow to learn from: a missed check costs a push, a wait and another push. `scripts/ci_local.py` runs the same checks locally, but only the ones this branch's changes need. Claude Code and Cursor run it for agents through hooks, before work leaves the machine.

## `scripts/ci_local.py`

It compares the working tree (committed, uncommitted and untracked files) with `origin/main` and picks checks by path:

| Check | Runs when | What it runs (as CI does) |
| --- | --- | --- |
| `agent-config` | `.claude/` or `.cursor/` changed | `scripts/sync_agent_config.py --check` |
| `backend-lint` | a backend `.py` file changed | black, flake8 and pylint on the changed files (CI lints all of `backend/`) |
| `backend-tests` | anything under `backend/` changed | the tests of the apps the diff changes, the apps that import a changed module, and `app.tests` (`--parallel auto`, migration tests excluded); the whole suite for a change outside an app (settings, Pipfile, test runner) or with `--full-backend`; then `--tag migration` when a migration changed. GitHub CI always runs the whole suite. |
| `backend-tests` (`app.tests` only) | docs, READMEs, agent config, `scripts/`, `.github/`, desktop contract files or `openapi.json` changed | the repo-wide tests in `backend/app/tests/` (docs, PR checklist, schema) |
| `bot` | `bot/` changed | flake8 and the bot's unittest suite |
| `voice` | `voice/` changed | flake8 and the voice service's unittest suite (the real-Murmur lab runs in CI only) |
| `frontend-tests`, `frontend-types` | `frontend/app/` changed | `npm run test -- --run` and `npm run check`; the type check is skipped when the changes are only Markdown, `public/` files or translation edits that remove no key |
| `desktop` | `desktop/` changed | `npm test` and the version check |
| `rust-browser` | only with `--rust` | builds Rust and plays every story in Chromium |

```bash
python3 scripts/ci_local.py
```

```bash
python3 scripts/ci_local.py --list
```

`--all` runs every check, `--only backend-lint,frontend-types` picks some, and `--no-cache` ignores earlier passes. Checks run side by side. A passing check is remembered for that exact tree, so running it again on the same files is instant. The pass record and each check's full log are kept in the git directory, under ci_local/ (the worktree's own git directory in a worktree). A missing virtualenv (`pipenv sync --dev`) or `node_modules` (`npm ci`) is installed on first use. Hooks run without your login shell, so when the `node` on PATH is older than CI's Node 22, the checks use one from nvm (`~/.nvm/versions/node/`) instead.

Backend tests never run on the cached database itself. `backend/ci_test_db.py migrate` keeps `backend/.test-db/template.sqlite3` migrated and nothing else, and each run empties `.test-db/run/` (the parallel workers' clones included) and copies it there first, so rows a run leaves behind (a `TransactionTestCase` flush, a crashed worker, the migration tests) can't fail the next one. A warm run takes seconds to under a minute (the whole suite is about 40 seconds); the first run in a new worktree builds the template and takes about three.

## The hooks

`scripts/agent_hooks.py` holds both hooks, for both clients. They are registered in `.claude/settings.json`, and `scripts/sync_agent_config.py` generates `.cursor/hooks.json` from it (edit the Claude file, then run the sync).

- **Before a shell command** (Claude `PreToolUse` on Bash, Cursor `beforeShellExecution`). Claude starts the hook only for the commands it checks: each handler has an `if` filter (`Bash(git push*)`, `Bash(git -C *)`, `Bash(gh pr *)`, `Bash(gh issue create*)`) and passes its kind (`push`, `pr`, `issue`), so a compound `git push && gh pr create` is checked once per part. Cursor has no `if`, so `sync_agent_config.py` turns these into one unfiltered hook that checks every kind:
  - `git push` runs `ci_local.py`. Deleting a branch, pushing tags and dry runs are not checked.
  - `gh pr create` and `gh pr ready` run `scripts/check_pull_request.py` on the description, not the CI checks: the push before them already ran those. Drafts skip the description, as CI does.
  - `gh pr edit --body ...` checks only the description, and not on a draft.
  - `gh issue create` runs `scripts/check_issue.py` on its `--label`s and body: at least one type label from `.github/labels.json`, and for a significant feature a design link or a person's sign-off (`.claude/rules/issues.md`). `--web` isn't checked; the browser form sets the labels.
  - A failure blocks the command and tells the agent what failed.
  - The hook reads the description from `--body-file`, from a heredoc (`--body "$(cat <<'EOF' ...)"`) or from a quoted `--body`. When it can't read it, it asks for `--body-file`.
- **Issue claims** (`scripts/issue_claims.py`, so two people or their agents don't build the same thing):
  - **When a prompt names an issue** (Claude `UserPromptSubmit`, Cursor `beforeSubmitPrompt`), as `#123`, `issue 123` or an issues URL, the hook looks it up with `gh`. When someone else looks to be on it (assigned, an open pull request of theirs references it, or a comment of theirs in the last 30 days says so), the person is shown who. Claude is also told to ask before changing code for it, and to claim an unclaimed issue before working on it: `gh issue edit N --add-assignee @me` with triage access or more, else a comment. Cursor's prompt hook can only show the warning.
  - **Before `gh pr create`**, every open issue the description closes or refers to must be claimed by the person opening it (assigned, or a comment of theirs); the hook blocks with the command to run. When someone else looks to be on one, the person is asked to confirm (`ask`) instead of the command running straight away.
  - The issues are looked up on the `upstream` remote's repository when there is one (a fork), otherwise `origin`'s. Both `github.com` URLs and SSH host aliases (`git@github-work:owner/repo.git`) are understood.
  - When `gh` is missing, signed out or offline, the claim checks say nothing and block nothing.
- **After a file edit** (Claude `PostToolUse` on Edit/Write, Cursor `postToolUse` on Write): a backend `.py` file is formatted with black, silently, and a backend or bot `.py` file is checked with flake8 (`bot/` isn't black-formatted). Only flake8 errors go back to the agent. The hook doesn't tell it to re-read a reformatted file: Claude Code notices the change and asks for a re-read only when the next edit needs one.

Hook output goes into the agent's context, so it is kept short: nothing on success, the last 40 lines of a failing check (with the path to its full log), and one line when a virtualenv or pipenv is missing.

To push without the checks (for a person, not an agent), prefix the command with `CI_LOCAL_SKIP=1`.

Cursor documents hooks for cloud agents too, from the repo's `.cursor/hooks.json`. Its `afterFileEdit` event can't send anything back to the agent, so the edit hook uses `postToolUse`.

## Not hooks

The `backend-review` and `frontend-review` skills need judgment, so they stay skills. The hook only checks that their results are in the description. The Rust component library justification has to come from a person (`.claude/rules/pull-requests.md`), so the hook blocks without it rather than letting an agent write it.

`backend/app/tests/test_agent_hooks.py` tests the command parsing, the client replies and the check selection.
