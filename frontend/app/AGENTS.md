# Frontend AI rules

Full methodology: **`../../docs/frontend-design.md`** (read it before editing UI). Non-negotiable rules:

## Interactivity & state
- **htmx owns all server state.** Data fetching, mutations, partial re-renders, DOM updates → htmx (`hx-*`, `hx-swap-oob`, `htmx.process()`) against partials in `src/pages/partials/*_component.astro`. Server renders HTML; never build DOM from JSON.
- **Alpine = minor, local UI only**: toggles, collapsibles, filters, dialog open/close.
- **Never** use Alpine to call endpoints (`fetch()`/axios) or hold/drive DOM from server data. If data must change the DOM, use an htmx partial.
- After htmx injects a partial, re-init Alpine/htmx with `htmx.process()` / `Alpine.initTree()`.

## Naming
- **snake_case** for props, variables, functions, files. **PascalCase** for interfaces and data types only.

## Styling
- Never hardcode colors/spacing/type — use the CSS custom properties in `src/styles/properties/` (`--fleet-red`, `--space-*`, `--step-*`, fonts, transitions). No raw px/rem for spacing/type, no hand-rolled hex.
- Z-index only via the layered chain in `_z-index.scss`. Transparency via the `.*-transparency` effect classes.
- Compose layout from `src/components/compositions/` (`Wrapper`, `Grid`, `FlexInline`, `Flexblock`, `FixedFluid`, `Cover`, `ScrollX`, …) rather than hand-rolling.
- Reuse `Button`, `Badge`, `Tag`, `Card`, `Input`; one `.astro` component per file; scoped `<style lang="scss">` (`is:global` only for shared classes); `define:vars` to pass props into CSS.

## Accessibility
- Dark-only; respect `body.color-blind-mode`; keep `:focus-visible`; gate hover effects behind `@media (hover: hover)` and tactile press behind `@media (hover: none)`.

## Verify
From this directory: `npm run check` and `npm run test`. Don't finish until `npm run check` passes.
