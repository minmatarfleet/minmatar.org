## Summary

<!-- What changed and why, for a reviewer who hasn't seen the work. Link the design, wireframe, or help ticket. -->

<!--
The sections below are checked by .github/workflows/pull-request.yml (scripts/check_pull_request.py).
Keep the headings and checkbox wording as they are; tick with [x]. Draft pull requests are checked when they are marked ready.
-->

## Issue

<!--
"Closes #123" when merging this pull request finishes the issue (GitHub closes it on merge).
"Refs #123" when it is part of an issue, or related to one, and the issue stays open. One issue per line.
No issue: tick the box and say why on the Issue line below (a Sentry fix, a help ticket link, a follow-up to #N's review).
-->

- [ ] No issue for this change

Issue:

## Frontend review

<!-- Required when the pull request changes frontend/app/. Run the frontend-review skill (.claude/skills/frontend-review/SKILL.md) on the final diff, fix what it finds, and paste its result. -->

- [ ] No website changes
- [ ] Ran the frontend review on the final diff

Result:

## Backend review

<!-- Required when the pull request changes backend/ or bot/. Run the backend-review skill (.claude/skills/backend-review/SKILL.md) on the final diff, fix what it finds, and paste its result. -->

- [ ] No backend changes
- [ ] Ran the backend review on the final diff

Result:

## Rust component library

<!--
Required when the pull request adds a component to frontend/app/rust/library.ts, changes a component listed there or a composition,
or changes a design token (frontend/app/src/styles/properties/). Feature blocks don't count.
The justification is written by a person, not an agent: why the existing library could not be used as is, or why the shared component
or token has to change. An agent asks for it and records the person's words.
-->

- [ ] No shared component or token changed
- [ ] This pull request adds or changes a shared component or token

Components / tokens:

Human justification:

Justified by: @

## Documentation

<!-- Docs that describe what this pull request changes change with it: docs/, READMEs, .claude/rules, skills, the docs index (docs/README.md). -->

- [ ] Updated the docs this change affects
- [ ] No documented behaviour changed

Docs updated, or why none needed:

## Verification

<!-- Tick what you ran locally; CI runs these too. Leave a line unticked when it doesn't apply. -->

- [ ] Backend tests and black / flake8 / pylint
- [ ] `npm run test` and `npm run check` in frontend/app
- [ ] Migration tests (`--tag migration`) for a changed migration
- [ ] OpenAPI schema and website API types regenerated for a changed endpoint
- [ ] Desktop contract files regenerated, or desktop version bumped, when the desktop is affected
- [ ] Looked at the change in a browser
