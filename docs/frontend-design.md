# Frontend Design & Methodology

Source of truth for building and editing the web frontend (`frontend/app/`). AI agents and humans must follow these rules so new UI matches the existing design system. Scope: the Astro web frontend only. The mobile Expo app has its own conventions.

## Tech stack

| Concern | Choice |
| --- | --- |
| Framework | [Astro 5](https://astro.build/) (SSR, `@astrojs/node` standalone) |
| Styling | Scoped SCSS per component (`<style lang="scss">`) + Tailwind v4 utilities (`@tailwindcss/vite`) |
| Design tokens | CSS custom properties under `src/styles/properties/` |
| Layout | Every-Layout-style composition components in `src/components/compositions/` |
| Interactivity | Alpine.js (minor local UI) + htmx (server-driven state/partials) |
| Typing | TypeScript strict (`strictNullChecks`), shared types in `src/types/` |
| Tests | Vitest (`npm run test`) |

Path aliases (see `tsconfig.json`): `@components/*`, `@layouts/*`, `@dtypes/*` (`src/types/`), `@helpers/*`, `@i18n/*`, `@api/*`, `@json/*`, `@markdown/*`, `@images/*`, `@/*`.

## 1. Interactivity & state management (primary rule)

This is the reason this spec exists. Recent changes introduced Alpine `fetch()` callers that duplicate server data client-side; that pattern is **forbidden** going forward.

### htmx owns all server state

- Any data fetching, mutation, partial re-render, or DOM update that reflects server state is handled **server-side via htmx**:
  - `hx-get` / `hx-post` / `hx-put` / `hx-patch` / `hx-delete` on the element that triggers the exchange
  - `hx-swap` (`innerHTML`, `outerHTML`, `transition:true`) and `hx-swap-oob="true"` for out-of-band updates to `id`-targeted nodes
  - Server-rendered partials live under `src/pages/partials/*_component.astro` and are requested via `PARTIAL_URL` constants
- The server renders the resulting HTML; the client never reconstructs DOM from JSON.
- When htmx injects a partial that contains Alpine or htmx markup, re-initialize it: `htmx.process(element)` (and `Alpine.initTree(element)` if Alpine was added). Existing example: `src/components/partials/AlpineScripts.astro`.

### Alpine is for minor, local interactivity only

Use Alpine for transient **UI-only** state that requires no server data:

- Toggles, collapsibles (`x-show`, `x-collapse`), accordions
- Filters that operate on already-rendered DOM
- Dialog / modal open-close, focus trapping (`x-trap`), `aria-hidden` toggling
- Small view-layer state like `expanded`, `modal_open`, `tab`/`active`

### Forbidden

- ❌ Alpine calling endpoints: no `fetch()` / axios / `$nextTick(fetch...)` inside `x-data` for server data.
- ❌ Holding server data in Alpine state and driving DOM updates from it.
- ❌ Client-side rendering of server records (cards, tables, lists) from fetched JSON.
- ❌ Duplicating server data that already exists in an htmx partial.

If data must change the DOM, use an **htmx partial + OOB swap** instead.

### Migration

Existing Alpine `fetch()` callers predate this rule and must be migrated to htmx partials opportunistically:

- `src/components/blocks/LoyaltyOrderBook.astro`
- `src/components/blocks/PageProgressTracker.astro`
- `src/components/partials/LearningAlpine.astro`
- `src/components/blocks/NotificationPreferences.astro`
- `src/pages/account.astro`
- `src/pages/industry/orders/planner.astro`

Migration pattern: move the rendering logic into `src/pages/partials/*_component.astro`, expose a `PARTIAL_URL`, and trigger it with `hx-get`/`hx-post` + `hx-swap`, using `hx-swap-oob` for independent regions.

## 2. Naming conventions

- **snake_case** for props, variables, functions, CSS custom properties, and files.
  - ✅ `padding_inline`, `min_item_width`, `row_gap`, `max_width`, `cover_image`
  - Some legacy components use camelCase (e.g. `minHeight`, `noPad`); **new code uses snake_case**.
- **PascalCase** for TypeScript **interface names** (`PageCoverOptions`, `FleetUI`, `CorporationBasic`) and **data types / type aliases** (`ButtonColors`, `ButtonSizes`, `TagColors`, `spaces`).
- Component files: `Name.astro`, one component per file.
- Partial pages: `snake_case_component.astro` under `src/pages/partials/`.
- Bracket group classes use `[ lowercase-hyphenated ]` (see component conventions).

## 3. Design tokens

Never hardcode colors, spacing, type sizes, or fonts. Use the tokens below, which are defined in `src/styles/properties/` and loaded by `src/styles/base.scss`.

### Colors (`_colors.scss`)

```css
--fleet-yellow  #f1d9a0   --fleet-red  #b53620   --alliance-blue #2051B5
--militia-purple #7342B2  --green      #198754   --black #121212
```

- Color-blind overrides: `--fleet-red-blind #e8590c`, `--green-blind #0d6efd`. Applied automatically via `body.color-blind-mode` (do not hardcode the blind-safe color; toggle the token).
- EVE meta groups: `--tech-i`, `--tech-ii`, `--storyline`, `--faction`, `--officer`, `--deadspace`, `--tech-iii`, `--abyssal`.
- Security status: `--security-status-1` … `--security-status-null`.
- Semantic: `--foreground` (default `--fleet-yellow`), `--background` (black), `--component-background` (`rgb(25,25,25)`), `--highlight` (white), `--faded`, `--button-color`, `--form-color`, `--border-color`, `--border-color-hover`.

### Fonts (`_font-families.scss`, `_fonts.scss`)

| Token | Font | Use |
| --- | --- | --- |
| `--heading-font` | Norwester | Headings (uppercase) |
| `--button-font` | Montserrat | Buttons |
| `--badge-font` / `--tag-font` | Norwester | Badges, tags |
| `--countdown-font` | Qahiri | Countdowns |
| `--default-font` / `--content-font` | Montserrat | Body |

### Fluid scales (`src/styles/utopia/`)

- Space: `--space-3xs` … `--space-3xl`, plus one-up pairs (`--space-3xs-2xs` … `--space-2xl-3xl`) and custom `--space-s-l`. Full list is typed as `spaces` in `src/types/layout_components.ts`.
- Type: `--step--2` … `--step-5` (fluid `clamp()` values).
- ✅ Use `var(--space-s)`, `var(--step-1)`. ❌ Never use raw `px`/`rem` for spacing or type.

### Layout widths (`_layout.scss`)

`--max-content-width` (1920px), `--max-col-width` (70rem), `--max-text-width` (60rem), `--max-landing-width` (49rem), `--max-video-description-width`, `--component-padding-block`, `--component-block-gap`, `--sticky-top` (156px).

### Transitions (`_transitions.scss`)

`--fast-transition` (0.1s), `--normal-transition` (0.3s), `--slow-transition` (1s), `--slowest-transition` (8s cubic-bezier).

### Z-index (`_z-index.scss`)

Layered, additive chain. Never invent z-index values; derive from the chain:

```
--base-z-index (10000)
  └─ --header-z-index
      └─ --neocom-z-index
          └─ --backdrop-z-index
              └─ --dialog-z-index
                  └─ --page-finder-z-index
                      └─ --alert-z-index
                          └─ --dialog-close-z-index
                              └─ --tooltips-z-index
--sticky-z-index = --base-z-index
```

### Effects / transparency (`_effects.scss`)

Transparency utilities are classes, not tokens: `.light-transparency`, `.light-transparency-heavier`, `.transparency`, `.dark-transparency`, `.darker-transparency`, `.solid-transparency`. On mobile they render a solid background; at `≥980px` they apply `backdrop-filter: blur(...)`. Prefer these over hand-rolled `rgba` + blur.

## 4. Layout methodology

Compose layout from the primitives in `src/components/compositions/` instead of hand-rolling flex/grid per component. Each accepts design-token props (snake_case) and passes through extra attributes.

| Composition | Purpose |
| --- | --- |
| `Wrapper` | Page/block container: `padding_inline` (default `var(--space-2xl-3xl)`), `padding_block`, `max_width` (default `80rem`), `centered`, `neocom` (reserves space for the neocom sidebar) |
| `Grid` | Auto-fit grid: `row_gap`, `column_gap`, `min_item_width` (default `10rem`); `.grid-fill` switches to auto-fill. Uses `minmax(min(var(--min), 100%), 1fr)` |
| `FlexInline` | Horizontal flex row that wraps: `gap`, `justification` |
| `Flexblock` | Vertical flex column with child gutters (`gap` selects a `gap-*` class): `centered`, `first_element_gap`, `.push-bottom` on children |
| `FixedFluid` | Media-object: fixed-width first child (`width`) + fluid remainder; `fluid_first` reverses |
| `FluidFixed` | Fluid first child + fixed-width last child |
| `Cover` | Full-height column (min-block-size 100vh) that vertically centers the body between `header`/`footer` slots |
| `Center` | Centering wrapper (flex, justify + align center) |
| `ScrollX` | Horizontal scroll region with `min_content_width` |
| `AspectRatio` | Box that preserves `horizontal`/`vertical` ratio |
| `BlockList` | Vertical stack of full-width children with a uniform `gap` |

Rules:

- Prefer composing existing primitives over adding bespoke layout CSS.
- Pass spacing via tokens, not literal values.
- Reuse `Button`, `Badge`, `Tag`, `Card`, `Input` etc. instead of restyling raw elements.

## 5. Component conventions

A component lives in `src/components/` (`blocks/`, `page/`, `partials/`, `compositions/`, `layout/`, `icons/`, `logos/`). One component per file.

Canonical skeleton:

```astro
---
import type { SomeType } from '@dtypes/layout_components'

interface Props {
    title:            string;
    size?:            number;
    [propName: string]: any;
}

const {
    title,
    size = 64,
    ...attributes
} = Astro.props;

delete attributes.class
---

<div class:list={['my-component', Astro.props.class]} {...attributes}>
    <slot />
</div>

<style lang="scss" define:vars={{ my_component_size: size }}>
    .my-component {
        width: var(--my_component_size);
    }
</style>
```

Conventions:

- `interface Props` with snake_case fields and defaults destructured from `Astro.props`; `[propName: string]: any` allows attribute passthrough.
- `delete attributes.class` so the caller's `class` is re-applied via `class:list={[...]}`, never overwritten.
- Bracket notation groups classes for readability: `class:list={['[ button ]', { narrow: narrow }, Astro.props.class]}`.
- `define:vars` maps props to **scoped** CSS custom properties (`lang="scss"`). Global/shared classes use `lang="scss" is:global` — reserve it for truly shared patterns.
- Tailwind is used for utility classes only; reference tokens via arbitrary values (e.g. `top-[var(--space-2xs)]`, `min-w-[100px]`, `text-highlight`). No `@apply` for whole components; no hand-rolled color/space literals.
- i18n: `import { i18n } from '@helpers/i18n'; const { t, translatePath } = i18n(Astro.url)`. User-visible strings go through `t(...)`; internal URLs through `translatePath(...)`.
- Shared UI types (colors, sizes, spaces) come from `@dtypes/layout_components` (`ButtonColors`, `ButtonSizes`, `TagColors`, `spaces`, `FlexInlineJustify`, `PageCoverOptions`, ...).
- Alpine directives (`x-data`, `x-on`, `x-show`, `x-collapse`, `x-trap`, `x-bind`) are for local UI state only — see rule 1.
- htmx attributes (`hx-*`) for anything that reads/writes server state.

## 6. Accessibility & behavior

- Dark-only theme: `color-scheme: dark`; body foreground/background from tokens (`--foreground` / `--background`).
- Color-blind mode: detect nothing manually — class `body.color-blind-mode` swaps the tokens automatically.
- Focus: keep default `:focus-visible` outlines (double outline on links, `outline: none` only when an explicit visible alternative exists, e.g. buttons scale on focus).
- `SkipToContent` exists; main content is `id="content"`.
- `.visually-hidden` for screen-reader-only text.
- Interaction media queries:
  - `@media (hover: hover)`: hover/focus scale effects (e.g. buttons `transform: scale(1.05)`).
  - `@media (hover: none)`: tactile press states (`scale(0.95)` on active).
- Dialogs/modals: focus-trap with `x-trap`, `aria-hidden` while closed, `inert` binding, Escape to close.

## 7. Verification

Run from `frontend/app/`:

```bash
npm run check      # astro check --minimumSeverity error
npm run test       # vitest
```

Do not merge frontend changes that fail `npm run check`.
