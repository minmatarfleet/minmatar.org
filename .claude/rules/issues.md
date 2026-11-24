# GitHub issues

Issues are read by people deciding what to work on, so the labels say what kind of work it is, not which part of the
code it touches. The labels live in `.github/labels.json` (synced to GitHub by `.github/workflows/labels.yml`); people
open issues from the forms in `.github/ISSUE_TEMPLATE/`.

## Type labels

Give every issue at least one, with `--label` on `gh issue create`:

| Label | Use for |
| --- | --- |
| `feature` | A new capability, or a change to how something works |
| `bug` | Something is broken or shows the wrong thing |
| `user-feedback` | Raised by a pilot (help ticket, Discord, a meeting). Add `feature` or `bug` once it is clear which |
| `security` | Access control, secrets, hardening. The repository is public: describe the work, never the exploit |
| `tech-debt` | Cleanup, refactor, upgrade, tooling: nothing pilots should notice |

`backend` and `frontend` are optional; don't use them instead of a type. Status labels (`needs-triage`,
`needs-design`) are set by `.github/workflows/issues.yml`; don't add or remove them by hand.

## Features need a design, or a person's sign-off

A **significant** feature (a new page, tab or flow, or a reworked layout) needs a design before it is built. Before
opening one, **ask the person** (AskUserQuestion): make a Claude design first (recommended), or will they sign off
building it without one?

- **Design**: make it (a wireframe canvas or design artifact, rendered and checked) and link it under `### Design`.
- **Sign-off**: tick the box under `### Design sign-off` and record their GitHub handle and their reason under
  `### Signed off by`. Never sign off yourself, and never invent the reason.

Small changes inside an existing page and backend-only work don't need either: say so under `### Size`.

Write the body with the issue form's headings, so the check and the workflow can read it:

```markdown
### Problem

What pilots can't do today, and who it is for.

### Proposal

What exists when this is done; what is out of scope.

### Size

Significant: a new page, tab or flow, or a reworked layout

### Design

https://claude.ai/artifact/...

### Design sign-off

- [ ] A person decided this ships without a design

### Signed off by

### Context

Links, related issues, data.
```

`Size` starts with `Significant`, `Small` or `Nothing visible`; a feature without one is treated as significant.

## The hook

`scripts/agent_hooks.py` runs `scripts/check_issue.py` before `gh issue create` and blocks it without a type label,
or for a significant feature without a design link or a person's sign-off. Pass the body with `--body-file`.

```bash
python3 scripts/check_issue.py --labels feature --body-file issue.md
```
