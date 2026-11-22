// Every component in the Rust library has a stories file, filed under its
// category, whose meta.component is that component, with enough stories to
// show its props and a docs description.
import { describe, expect, test } from 'vitest'
import { existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { RUST_LIBRARY } from '../../rust/library'
import { source_files } from '../conventions/scan'

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

// Every library component is imported by some file under src/ (its own file aside).
// A component with no caller is retired or waiting for one: list it here with the
// reason. Once it gains a caller, the test below fails until it is removed.
const UNUSED_ALLOWLIST: Record<string, string> = {
    'blocks/sde/TypeSearch': 'retired or given a caller in this PR (W5/W6)',
    'blocks/sde/SolarSystemSearch': 'retired or given a caller in this PR (W5/W6)',
    'blocks/sde/TypeResults': 'the search partials emit Combobox options now; read-only and linking result lists wait for a caller (W9)',
    'blocks/sde/SolarSystemResults': 'the search partials emit Combobox options now; read-only and linking result lists wait for a caller (W9)',
    // Not in the W2 brief's list: no src/ file references it on this branch. Confirm with the owner before W5/W6 land.
    'blocks/InputError': 'no caller under src/ on feat/rust-library-alignment; confirm with the owner',
}

const COMPONENTS_DIR = 'src/components'
const ENTRIES = Object.values(RUST_LIBRARY).flat()

// `from '…'`, `import '…'` and `import('…')`, the same specifier forms the aliases and relative paths use.
const IMPORT_SPECIFIER = /(?:^|[\s;])(?:import|from)\s*\(?\s*['"]([^'"\n]+)['"]/gm

/** The component (src/components path, no extension) an import specifier names, or null. Resolves @components/ and relative paths. */
function imported_component(specifier: string, importer: string): string | null {
    const target = specifier.startsWith('@components/')
        ? join(COMPONENTS_DIR, specifier.slice('@components/'.length))
        : specifier.startsWith('.')
          ? join(dirname(importer), specifier)
          : null
    return target?.startsWith(COMPONENTS_DIR + '/') ? target.replace(/\.astro$/, '') : null
}

const importers = new Map<string, Set<string>>()
for (const file of source_files()) {
    for (const match of file.text.matchAll(IMPORT_SPECIFIER)) {
        const component = imported_component(match[1], file.path)
        if (!component) continue
        if (!importers.has(component)) importers.set(component, new Set())
        importers.get(component)!.add(file.path)
    }
}

describe('Rust library: every entry is used under src/', () => {
    test('UNUSED_ALLOWLIST only names library entries', () => {
        for (const entry of Object.keys(UNUSED_ALLOWLIST))
            expect(ENTRIES, `${entry} is not in rust/library.ts`).toContain(entry)
    })

    for (const entry of ENTRIES) {
        test(entry, () => {
            const component = join(COMPONENTS_DIR, entry)
            const callers = [...(importers.get(component) ?? [])].filter((path) => path !== `${component}.astro`)
            if (entry in UNUSED_ALLOWLIST) {
                expect(callers, `${entry} is in UNUSED_ALLOWLIST but now has a caller; remove it from the list`).toEqual([])
                return
            }
            expect(callers, `${entry} is not imported under src/; use it, retire it, or add it to UNUSED_ALLOWLIST with a reason`).not.toEqual([])
        })
    }
})
