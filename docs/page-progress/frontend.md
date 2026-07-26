# Page Progress — Frontend Guide

Track whether users have read sections of a page. Progress is shown as a percentage in the UI. For signed-in users it is also stored server-side and appears in Django admin (**User page progress**: Username | Page | Progress%).

For the system design (models, endpoints, merge-on-login flow), see [architecture.md](architecture.md).

Anonymous visitors are tracked in **localStorage** on this device. When they log in, that stash is **union-merged** into their user account and then cleared.

## How it works

1. You declare a stable `page_key` and a list of `section_ids`.
2. Section elements in the DOM are marked with matching `data-section-id` values.
3. When a visitor keeps a section sufficiently on screen (~1s dwell, ≥50% visible), the section is marked read (localStorage if anonymous; API if authenticated).
4. Progress % = `round(100 × sections_read / section_total)`.
5. Optional **Mark as read** acknowledgement (`require_ack`, default `true`) appears after all sections are read.

There is no page registry in the database — the frontend supplies `page_key`, title, version, and sections.

## Frontend wiring (3 steps)

1. Build a manifest with `pageProgressFromMarkdown` or `pageProgressFromSections`.
2. Put `data-page-progress-root` on a parent that wraps the tracker **and** the sections.
3. Mount `<PageProgress {...progress} />` and mark sections in the DOM.

Imports:

```ts
import {
  pageProgressFromMarkdown,
  pageProgressFromSections,
} from '@helpers/pageProgress'
import PageProgress from '@components/blocks/PageProgress.astro'
import PageProgressSection from '@components/blocks/PageProgressSection.astro'
```

`<PageProgress />` handles auth cookies and i18n labels. It mounts whenever `section_ids` is non-empty (anonymous or signed-in).

---

### Example A — Markdown page with `##` headings

Best for long-form docs that already use `##` as section breaks (guides, values, etc.).

```astro
---
import { pageProgressFromMarkdown } from '@helpers/pageProgress'
import PageProgress from '@components/blocks/PageProgress.astro'

const page_title = 'Alliance Values'
const { html, ...progress } = pageProgressFromMarkdown({
  page_key: 'alliance/values',
  page_title,
  markdown: rawMarkdown,
})
---

<div data-page-progress-root>
  <h1>{page_title}</h1>
  <PageProgress {...progress} />
  <div class="prose" set:html={html} />
</div>
```

`pageProgressFromMarkdown`:

- Extracts each `##` heading as a section id (slugified title).
- Returns tagged HTML where every `h2` already has `id` + `data-section-id`.
- Sets `version` from a hash of the markdown (content changes reset progress for that version).

Destructure `html` out before spreading into `<PageProgress />` so you do not pass HTML as a component prop.

**Live reference:** `frontend/app/src/pages/guides/[name].astro`, `frontend/app/src/pages/alliance/values.astro`

---

### Example B — Custom Astro page with explicit sections

Best for bespoke layouts (ship guides, multi-component pages).

```astro
---
import { pageProgressFromSections } from '@helpers/pageProgress'
import PageProgress from '@components/blocks/PageProgress.astro'
import PageProgressSection from '@components/blocks/PageProgressSection.astro'

const page_title = 'Example Page'
const progress = pageProgressFromSections({
  page_key: 'examples/demo',
  page_title,
  sections: [
    { id: 'intro', title: 'Introduction' },
    { id: 'details', title: 'Details' },
    { id: 'summary', title: 'Summary' },
  ],
  // Optional: bump version when content changes beyond section ids
  version_source: JSON.stringify({ edition: '1.0', sections: ['intro', 'details', 'summary'] }),
})
---

<div data-page-progress-root>
  <h1>{page_title}</h1>
  <PageProgress {...progress} />

  <PageProgressSection id="intro">
    <h2>Introduction</h2>
    <p>…</p>
  </PageProgressSection>

  <PageProgressSection id="details">
    <h2>Details</h2>
    <p>…</p>
  </PageProgressSection>

  <!-- Equivalent low-level marking: -->
  <section id="summary" data-section-id="summary">
    <h2>Summary</h2>
    <p>…</p>
  </section>
</div>
```

`sections` may be a list of id strings or `{ id, title? }` objects. Every id in the manifest must exist as `data-section-id` somewhere under `data-page-progress-root` (missing nodes are simply not observed until present).

**Live reference:** `frontend/app/src/pages/guides/navy-destroyer-metagame/index.astro`

---

### Example C — One logical page across multiple routes

Use one shared `page_key` and the **full** section list on every route. Only sections present in the current DOM can be credited; overall % still reflects the whole page.

```astro
---
import { pageProgressFromSections } from '@helpers/pageProgress'
import PageProgress from '@components/blocks/PageProgress.astro'

// All story sections across every chapter
const allSections = getChronicleProgressSections()

const progress = pageProgressFromSections({
  page_key: 'alliance/story',
  page_title: 'Our story',
  sections: allSections,
  version_source: JSON.stringify(allSections),
})
---

<div data-page-progress-root>
  <PageProgress {...progress} />
  <!-- Current chapter only renders some of the section nodes -->
  <RatChronicle activeChapterId={chapter.id} />
</div>
```

**Live reference:** `frontend/app/src/pages/alliance/story/[chapter_id].astro`

---

## Anonymous progress and merge on login

1. **Anonymous:** dwell and ack write to `localStorage` key `minmatar.page_progress.v1`. The progress bar still mounts.
2. **Login:** on the next authenticated page load with a tracker, the client POSTs all stashed pages to `POST /api/page-progress/import`, clears localStorage on success, then loads server status.
3. **Merge:** union of section ids; `section_total` = max(existing, incoming); ack if either side acknowledged. Never deletes existing server sections.
4. **Version:** if local `version` ≠ current page version, that local entry is discarded.

Cross-device anonymous progress and admin visibility of anonymous readers are out of scope.

---

## Choosing `page_key`

Use a stable, slash-separated key that will not collide with other pages:

| Page | Example `page_key` |
|------|--------------------|
| Markdown guide | `guides/{slug}` |
| Custom guide | `guides/navy-destroyer-metagame` |
| Alliance values | `alliance/values` |
| Alliance story | `alliance/story` |

Changing `page_key` creates a new progress row. Changing `version` (via markdown hash or `version_source`) starts a fresh version for that user/page.

## Optional props

| Prop | Default | Meaning |
|------|---------|---------|
| `require_ack` | `true` | After 100% section progress, show **Mark as read**. Pass `require_ack={false}` to track sections only. |

## Behaviour notes

- **Dwell:** A section counts after continuous visibility (~1s at ≥50% on screen). Tall sections use a viewport-coverage fallback. Fast scroll / TOC jumps alone do not inflate progress.
- **Root scope:** The tracker looks for `[data-section-id]` inside the nearest `[data-page-progress-root]` (falls back to `document`).
- **Logged out:** Tracker still mounts; progress stays in localStorage until login.

## Admin

Django admin → **User page progress**

- List: Username | Page | Progress%
- Detail: includes a condensed **Sections read** table (no separate section admin model)
- Anonymous-only readers do not appear until they log in and merge

## Key files

| Area | Path |
|------|------|
| Public helpers | `frontend/app/src/helpers/pageProgress/` |
| Local stash | `frontend/app/src/helpers/pageProgress/localStore.ts` |
| UI drop-in | `frontend/app/src/components/blocks/PageProgress.astro` |
| Section wrapper | `frontend/app/src/components/blocks/PageProgressSection.astro` |
| Tracker (internal) | `frontend/app/src/components/blocks/PageProgressTracker.astro` |
| Backend API | `backend/page_progress/` (`/api/page-progress/...`, including `/import`) |
