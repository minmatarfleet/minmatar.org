---
name: rust-components
description: >-
  Build or change website UI (frontend/app) with Rust, the Minmatar Fleet
  component library (Storybook at my.minmatar.org/rust). Use for any page,
  partial, component, layout or styling work on the Astro site: find the
  existing component before writing markup or CSS, use it the way its stories
  do, and add stories when you add or change a shared component or a feature
  block. Also use when asked about the design system, design tokens, colours,
  fonts, icons, images, or Storybook.
---

# Rust: build the site from the component library

Rust is the website's component library: every shared component, rendered live with its props, stories, tests and
docs. Source in `frontend/app/rust/`, deployed at https://my.minmatar.org/rust/. Rules in
`docs/frontend-design.md` (§4.2) and `.claude/rules/frontend-design.md`.

## 1. Find before you build

1. **Read `frontend/app/rust/CATALOG.md`.** One entry per component: what it's for, import, props with defaults,
   slots, and its stories. Search it by purpose ("empty", "menu", "tabs", "pager", "dialog", "security", "badge").
2. **Open the component's stories file** (path in the catalog). The stories are the canonical usage: `args` are
   the props, `args.slots` the slot content, and each story name is a supported state.
3. **Tokens, fonts, icons, images:** the Foundations pages are generated from the source. For values, read
   `frontend/app/rust/public/tokens.json` (every CSS custom property, DTCG format) or `src/styles/properties/`.
   Icons: `src/components/icons/`. Images and backgrounds: `rust/foundations/imagery_collections.ts` lists every
   folder under `public/images`.
4. **Feature blocks** (fleet lists, campaign boards, order books, ...) are under **Features** in Rust with test
   data: `frontend/app/rust/stories/features/<area>/`, fixtures in `rust/fixtures/features/<area>.ts`. Reuse those
   fixtures when you need realistic data shapes.

Order of preference: use a component as is → add a prop to it (and a story for the new state) → compose several →
only then write a new component.

## 2. Use it the site's way

- Layout from `Layout` (Wrapper, Grid, Flexblock, FlexInline, FixedFluid, XFadeScroll ...), never hand-rolled flex/grid.
- `Button`, `Input`, `Select`, `Tag`, `Badge`, `ComponentBlock` instead of styling raw elements.
- Empty lists: `EmptyState`. Failed partial fetch: `ErrorRefetch`. Deferred content: `LazyPartial`.
- Colours, space, type only from tokens; no hex, px or rem. If a colour you need has no token, add the token.
- htmx for server state, Alpine for local UI only (see the rules).

## 3. When you add or change a component

- **Shared component** (used by a second feature, or generic): add it to `frontend/app/rust/library.ts` under its
  category and write `rust/stories/<category path>/<Name>.stories.ts`: a docs description, `argTypes` for every
  prop, at least 3 stories, a `play()` test on each. Follow `rust/docs/WritingStories.mdx`.
- **Changed a shared component's props or states:** update its stories (a new prop gets a control and a story).
- **New or changed feature block that renders from props:** add or update its Features story with scenario
  stories (empty, typical, busy, edge cases) and typed fixtures.
- **Justify it in the pull request.** A new `library.ts` entry, a change to a listed component or a
  composition, or a token change needs a person's justification in the pull request's "Rust component library"
  section (`.claude/rules/pull-requests.md`). Ask the person for it and record their words; never write it.
- **Regenerate generated files:** `UPDATE_CATALOG=1 npx vitest run testing/rust/catalog.test.ts` (and
  `UPDATE_TOKENS=1 npx vitest run testing/rust/foundations.test.ts` after changing tokens).

## 4. Verify

From `frontend/app` (Node 22):

```bash
export $(cat .env.BUILDONLY)
RUST_STORY_FILTER=components/forms npx vitest run testing/rust   # the stories you touched, as tests
npx vitest run testing/rust                                       # all Rust checks: coverage, foundations, imagery, catalog
npm run check                                                     # type-check ratchet
npm run rust                                                      # look at it: Storybook on :6006
```

`npm run rust:build && npm run rust:serve-local` then `npm run rust:test-browser` runs every story in Chromium,
as CI does.
