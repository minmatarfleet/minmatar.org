# Local CI and agent hooks

CI runs every check on every pull request, which is slow to learn from: a missed check costs a push, a wait and another push. `scripts/ci_local.py` runs the same checks locally, but only the ones this branch's changes need. Claude Code and Cursor run it for agents through hooks, before work leaves the machine.

## `scripts/ci_local.py`

It compares the working tree (committed, uncommitted and untracked files) with `origin/main` and picks checks by path:

| Check | Runs when | What it runs (as CI does) |
| --- | --- | --- |
| `agent-config` | `.claude/` or `.cursor/` changed | `scripts/sync_agent_config.py --check` |
| `backend-lint` | a backend `.py` file changed | black, flake8 and pylint on the changed files (CI lints all of `backend/`) |
| `backend-tests` | anything under `backend/` changed | the whole suite (`--parallel auto --keepdb`, migration tests excluded), then `--tag migration` when a migration changed |
| `backend-tests` (`app.tests` only) | docs, READMEs, agent config, `scripts/`, `.github/`, desktop contract files or `openapi.json` changed | the repo-wide tests in `backend/app/tests/` (docs, PR checklist, schema) |
| `bot` | `bot/` changed | flake8 and the bot's unittest suite |
| `voice` | `voice/` changed | flake8 and the voice service's unittest suite (the real-Murmur lab runs in CI only) |
| `frontend-tests`, `frontend-types` | `frontend/app/` changed | `npm run test -- --run` and `npm run check` |
| `desktop` | `desktop/` changed | `npm test` and the version check |
| `rust-browser` | only with `--rust` | builds Rust and plays every story in Chromium |

```bash
python3 scripts/ci_local.py
```

```bash
python3 scripts/ci_local.py --list
```

`--all` runs every check, `--only backend-lint,frontend-types` picks some, and `--no-cache` ignores earlier passes. Checks run side by side. A passing check is remembered for that exact tree, so running it again on the same files is instant. The pass record and each check's full log are kept in the git directory, under ci_local/ (the worktree's own git directory in a worktree). A missing virtualenv (`pipenv sync --dev`) or `node_modules` (`npm ci`) is installed on first use. Hooks run without your login shell, so when the `node` on PATH is older than CI's Node 22, the checks use one from nvm (`~/.nvm/versions/node/`) instead.

A warm backend run takes under a minute; the first run in a new worktree migrates the test database (`backend/.test-db/`) and takes about three.

## The hooks

`scripts/agent_hooks.py` holds both hooks, for both clients. They are registered in `.claude/settings.json`, and `scripts/sync_agent_config.py` generates `.cursor/hooks.json` from it (edit the Claude file, then run the sync).

- **Before a shell command** (Claude `PreToolUse` on Bash, Cursor `beforeShellExecution`):
  - `git push` runs `ci_local.py`. Deleting a branch, pushing tags and dry runs are not checked.
  - In a Claude cloud session (`CLAUDE_CODE_REMOTE=true`), the first `git push` of a branch with the session's random name (`claude/quirky-ramanujan-mezmg0`) is blocked, before the checks run, until the agent renames it to say what the change does: `claude/<three to six words>-mezmg0`. The `claude/` prefix and the session id stay, because the cloud git proxy only accepts pushes to those. A branch already on the remote keeps its name, so an open pull request never loses its branch.
  - `gh pr create` and `gh pr ready` also run `scripts/check_pull_request.py` on the description. Drafts skip the description, as CI does.
  - `gh pr edit --body ...` checks only the description, and not on a draft.
  - A failure blocks the command and tells the agent what failed.
  - The hook reads the description from `--body-file`, from a heredoc (`--body "$(cat <<'EOF' ...)"`) or from a quoted `--body`. When it can't read it, it asks for `--body-file`.
- **After a file edit** (Claude `PostToolUse` on Edit/Write, Cursor `postToolUse` on Write): a backend `.py` file is formatted with black, and a backend or bot `.py` file is checked with flake8 (`bot/` isn't black-formatted). Errors go back to the agent.

To push without the checks (for a person, not an agent), prefix the command with `CI_LOCAL_SKIP=1`.

Cursor documents hooks for cloud agents too, from the repo's `.cursor/hooks.json`. Its `afterFileEdit` event can't send anything back to the agent, so the edit hook uses `postToolUse`.

## Not hooks

The `backend-review` and `frontend-review` skills need judgment, so they stay skills. The hook only checks that their results are in the description. The Rust component library justification has to come from a person (`.claude/rules/pull-requests.md`), so the hook blocks without it rather than letting an agent write it.

`backend/app/tests/test_agent_hooks.py` tests the command parsing, the client replies and the check selection.
