// Features (rust/stories/features/): feature blocks with fixture data. Each
// file needs a title under Features/, a docs description, two or more
// scenario stories and a play() on every story. The stories themselves
// render and run in stories.test.ts.
import { describe, expect, test } from 'vitest'

const sources = import.meta.glob<string>('../../rust/stories/features/**/*.stories.ts', { eager: true, query: '?raw', import: 'default' })

describe('Rust features', () => {
    for (const [path, source] of Object.entries(sources)) {
        test(path.replace('../../rust/stories/features/', ''), () => {
            expect(source, 'title must start with Features/').toMatch(/title:\s*'Features\/[^/']+\/[^']+'/)
            expect(source, 'needs parameters.docs.description.component').toMatch(/description:\s*\{[\s\S]*component:/)
            const stories = (source.match(/^export const \w+/gm) ?? []).length
            expect(stories, 'needs at least two scenario stories').toBeGreaterThanOrEqual(2)
            expect((source.match(/play:\s*(async|\w)/g) ?? []).length, 'every story needs a play()').toBeGreaterThanOrEqual(stories)
            // Data objects come from rust/fixtures/features/; a block whose props are
            // all scalars (a label, a flag) can set them inline.
            if (/:\s*\[\s*\{|\{\s*id:\s*\d/.test(source))
                expect(source, 'object data belongs in rust/fixtures/features/<area>.ts').toMatch(/fixtures\/features\//)
        })
    }
})
