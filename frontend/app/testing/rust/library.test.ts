// Every component in the Rust library has a stories file, filed under its
// category, whose meta.component is that component, with enough stories to
// show its props and a docs description.
import { describe, expect, test } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { RUST_LIBRARY } from '../../rust/library'

const sources = import.meta.glob<string>('../../rust/stories/**/*.stories.ts', { eager: true, query: '?raw', import: 'default' })

const MIN_STORIES = 3

function category_dir(category: string) {
    return category.toLowerCase().replace(/\s+/g, '-')
}

function story_component_import(source: string) {
    // meta.component, not a `component:` inside slot content elsewhere in the file.
    const meta = /export default \{([\s\S]*?)\n\}/.exec(source)?.[1] ?? ''
    const component_name = /^\s{4}component:\s*(\w+)/m.exec(meta)?.[1]
    if (!component_name)
        return null
    const import_match = new RegExp(`import\\s+${component_name}\\s+from\\s+['"]@components/([^'"]+?)(?:\\.astro)?['"]`).exec(source)
    return import_match?.[1] ?? null
}

const covered = new Map<string, { path: string; source: string }>()
for (const [path, source] of Object.entries(sources)) {
    // A story-only wrapper (a function prop can't reach the render server)
    // names the component it demonstrates: parameters.rust.covers.
    const component = /covers:\s*'([^']+)'/.exec(source)?.[1] ?? story_component_import(source)
    if (component)
        covered.set(component, { path, source })
}

for (const [category, components] of Object.entries(RUST_LIBRARY)) {
    describe(`Rust library: ${category}`, () => {
        for (const component of components) {
            test(component, () => {
                expect(existsSync(resolve(__dirname, '../../src/components', `${component}.astro`)), `src/components/${component}.astro is gone; update rust/library.ts`).toBe(true)

                const entry = covered.get(component)
                expect(entry, `no stories file has component: ${component}`).toBeTruthy()
                expect(entry!.path, `${component} stories belong in rust/stories/${category_dir(category)}/`).toContain(`/rust/stories/${category_dir(category)}/`)
                expect(entry!.source, `${component} stories need parameters.docs.description.component`).toMatch(/description:\s*\{[\s\S]*component:/)

                expect(entry!.source, `${component} stories need a title under '${category}/'`).toContain(`title: '${category}/`)

                const story_count = (entry!.source.match(/^export const \w+/gm) ?? []).length
                expect(story_count, `${component} needs at least ${MIN_STORIES} stories`).toBeGreaterThanOrEqual(MIN_STORIES)

                const play_count = (entry!.source.match(/play:\s*async/g) ?? []).length
                expect(play_count, `${component} stories need play() tests`).toBeGreaterThanOrEqual(Math.min(story_count, MIN_STORIES))
            })
        }
    })
}
