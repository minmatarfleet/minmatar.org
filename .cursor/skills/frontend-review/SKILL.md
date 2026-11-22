---
name: frontend-review
description: >-
  Standard code review for website changes (frontend/app: Astro pages,
  partials, components, helpers, styles, i18n, Rust stories). Run it on the
  final diff before opening or updating a pull request, and paste its Result
  block into the pull request's "Frontend review" section. Use when asked to
  review frontend code, review a PR's website changes, or fill in the PR
  template's frontend review.
---

# Frontend review

The review every pull request that touches `frontend/app/` gets before it is opened. It checks the diff against
the frontend rules, then runs the checks CI runs. The pull request template (`.github/pull_request_template.md`)
asks for its Result block, and `scripts/check_pull_request.py` fails the pull request without it.

Sources of truth: `docs/frontend-design.md`, `.claude/rules/frontend-design.md`, `.claude/rules/api-types.md`,
and the `rust-components` skill (`.claude/skills/rust-components/SKILL.md`). This skill is the checklist; those
documents are the rules. When they disagree, the documents win, and fix this skill.

## 1. Scope

```bash
git fetch origin main
git diff --stat origin/main...HEAD -- frontend/app
git diff origin/main...HEAD -- frontend/app
```

Review the **final** diff of the branch, not one commit. Read every changed file in full where the diff alone
hides the context (a changed prop: read its callers; a changed partial: read the page that loads it).

## 2. Correctness

Find bugs before style. For each changed file:

- Props: every caller passes what the component now expects; optional props have defaults; nullable API fields
  (`| null`) are handled, not assumed present.
- Data: types come from the generated API schema (`ApiResponse<...>`/`ApiRequest<...>` in
  `frontend/app/src/types/api.minmatar.org.ts`), never a hand-written interface. Dates from the API are ISO
  strings.
- Failure paths: a partial that fetches renders `ErrorRefetch` on failure; empty data renders `EmptyState`.
- Server state: htmx partials only. Look for `fetch(`, axios, or JSON-built DOM in Alpine code: forbidden.
- Swaps: no new `htmx:afterSwap` re-init scripts and no `htmx.process()` on swapped content (an
  `hx-trigger="load"` element would fire twice). `frontend/app/src/helpers/swap_init.ts` already initialises
  swapped content.
- Access: pages, partials, nav entries, tiles and buttons gate with `can(await get_gates(Astro), '<gate>')`;
  new gates are in `frontend/app/src/json/feature_gates.json` (`docs/auth/frontend-feature-gating.md`). No
  Django permission strings, no `is_superuser` checks. Per-object rights come from the API (`can_manage`, ...).
- Hidden data stays hidden: a field the API sends only to some viewers is rendered only for them.
- Strings: user-visible text goes through `t()` from `@helpers/i18n`, with keys in `frontend/app/src/i18n/ui.ts`.

## 3. Conventions

- **Rust first.** Every new piece of UI was looked up in `frontend/app/rust/CATALOG.md` first. Raw `<button>`,
  `<input>`, `<select>`, bordered panels and hand-rolled menus, tabs, pagers, dialogs or chips are findings when
  a Rust component does the job.
- **Shared components and tokens.** If the diff adds an entry to `frontend/app/rust/library.ts`, changes a
  component listed there, changes a composition (`frontend/app/src/components/compositions/`) or changes a design
  token (`frontend/app/src/styles/properties/`):
  - it has stories (≥3, `play()` tests, docs description) and the catalog is regenerated
    (`UPDATE_CATALOG=1 npx vitest run testing/rust/catalog.test.ts`; tokens: `UPDATE_TOKENS=1 npx vitest run
    testing/rust/foundations.test.ts`);
  - **the pull request records a human's justification** in its "Rust component library" section. You never
    write that justification. Ask the person why the existing library could not be used as is, or why the shared
    component has to change, and record their words and GitHub handle. If nobody has given one, the review
    result says so and the pull request is not ready.
  - A feature block (renders one feature, not in `library.ts`) needs a `Features/<Area>` story with fixtures
    when it renders from props, but no justification.
- **Layout** from compositions (`Wrapper`, `Grid`, `FlexInline`, `Flexblock`, `XFadeScroll`, ...), not
  hand-rolled flex/grid; wide tables and chip rows scroll inside `XFadeScroll`.
- **Tokens only.** No raw `px`/`rem` for spacing or type, no hex colours, no white/black `rgba()` tints, no
  invented z-index (derive from `frontend/app/src/styles/properties/_z-index.scss`).
- **Naming.** snake_case props, variables, functions, files and CSS custom properties; PascalCase types. Don't
  copy legacy camelCase props.
- **Component shape.** One component per file, `interface Props` with defaults destructured from `Astro.props`,
  `[propName: string]: any` passthrough, caller class re-applied with `class:list`, scoped SCSS by default,
  Tailwind utilities only (no `@apply` blobs).
- **Accessibility.** `:focus-visible` outlines kept; hover/scale effects behind `@media (hover: hover)`; nothing
  fights `body.color-blind-mode`; screen-reader text uses `.visually-hidden`.
- **No dead code.** Removed features take their components, helpers, i18n keys and stories with them.

## 4. Run the checks

From `frontend/app/` (Node 22):

```bash
export $(cat .env.BUILDONLY)
npm run test -- --run     # vitest: conventions ratchet, generated API types, Rust library and stories
npm run check             # astro check ratchet (testing/conventions/type_check_baseline.json)
```

If the backend schema changed, `npm run gen:api` must leave no diff. If Rust components or stories changed, also
run `RUST_STORY_FILTER=<folder> npx vitest run testing/rust` for the folders touched.

Look at the change in a browser when it is visible (`npm run dev`, or Storybook with `npm run rust`), at desktop
width and at 390px.

## 5. Fix, then report

Fix every finding you can. Anything left open is listed with the reason. Then write the result for the pull
request's "Frontend review" section, in this shape:

```text
Frontend review (frontend-review skill) on <short sha>:
- Fixed: <one line per fixed finding, or "nothing found">
- Open: <one line per finding left, with why, or "none">
- Checks: npm run test passed, npm run check passed
- Looked at: <pages/stories checked in the browser, or "not visible">
```

A review with open correctness findings, failing checks, or a missing Rust justification is not ready to merge:
say so in the result rather than ticking the box.
