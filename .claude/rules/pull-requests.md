# Pull requests

Every pull request description follows `.github/pull_request_template.md`, including ones opened with
`gh pr create --body` (the template is only pre-filled in the browser). `.github/workflows/pull-request.yml` runs
`scripts/check_pull_request.py` on it and fails when a control that applies is missing.

- **Issue**: under "Issue:" write `Closes #123` when merging the pull request finishes the issue (GitHub closes it),
  or `Refs #123` when it is part of one or related and the issue stays open; one per line. With no issue, tick "No
  issue for this change" and say why on that line (a Sentry fix, a help ticket link). Look for the issue first
  (`gh issue list --search`), and don't write `Closes` for an issue the pull request only partly does.
- **Website changes** (`frontend/app/`): run the `frontend-review` skill (`.claude/skills/frontend-review/SKILL.md`)
  on the final diff, fix what it finds, and paste its result under "Frontend review".
- **Backend changes** (`backend/`, `bot/`): run the `backend-review` skill (`.claude/skills/backend-review/SKILL.md`)
  the same way, under "Backend review".
- **Shared Rust components and tokens**: adding to `frontend/app/rust/library.ts`, changing a component listed
  there or a composition, or changing a token in `frontend/app/src/styles/properties/` needs a person's
  justification in the "Rust component library" section. **Never write it yourself.** Ask the person why the
  existing library could not be used as is (or why the shared component must change), and record their words and
  GitHub handle. Without one, the pull request isn't ready: say so instead of filling the section.
- **Documentation**: when the change alters anything a doc describes (`docs/`, READMEs, `.claude/rules`, skills),
  update that doc in the same pull request. The check lists docs that name the files you changed.
- Re-run the reviews after the last change, not before it: the results describe the final diff.

A hook (`scripts/agent_hooks.py`, see `docs/agent-ci-hooks.md`) runs `scripts/ci_local.py` before `git push`, and checks
the description on `gh pr create`, `gh pr ready` and `gh pr edit --body`. When it blocks a command, fix what it reports; never bypass it with `CI_LOCAL_SKIP=1` unless the person asks. Pass the
description with `--body-file` so the hook can read it.

Check the description locally before opening the pull request:

```bash
python3 scripts/check_pull_request.py --body-file body.md
```
