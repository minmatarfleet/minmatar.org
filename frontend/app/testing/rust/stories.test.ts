// Every Rust story is a test: it must render through Astro's Container API
// (as the Storybook render server does), leak no `undefined`/`[object Object]`
// into the page, and pass its play function against the rendered DOM with
// Alpine running. Stories tagged `browser` skip the play step here (they need
// htmx, layout or a real browser); `!test` skips the story entirely.
import { describe, expect, test } from 'vitest'
import { apply_decorators, render_story } from './render_story'
import { mount_story } from './story_dom'

type StoryModule = Record<string, any>

const loaders = import.meta.glob<StoryModule>('../../rust/stories/**/*.stories.ts')

// RUST_STORY_FILTER=forms/Button,data-display runs only the stories files
// whose path contains one of the parts.
const filter = process.env.RUST_STORY_FILTER
const modules: Record<string, StoryModule> = {}
for (const [path, load] of Object.entries(loaders)) {
    if (!filter || filter.split(',').some((part) => path.includes(part.trim())))
        modules[path] = await load()
}

const LEAKS = [/\bundefined\b/, /\[object Object\]/, /\bNaN\b/]

function visible_text(root: HTMLElement) {
    const clone = root.cloneNode(true) as HTMLElement
    clone.querySelectorAll('script, style, template').forEach((node) => node.remove())
    return clone.textContent ?? ''
}

test('Rust has stories', () => {
    expect(Object.keys(modules).length).toBeGreaterThan(0)
})

for (const [path, mod] of Object.entries(modules)) {
    const meta = mod.default
    const stories = Object.entries(mod).filter(([name, value]) =>
        name !== 'default' && !name.startsWith('__') && value && typeof value === 'object')

    describe(meta?.title ?? path, () => {
        test('has a title, a component and at least one story', () => {
            expect(meta?.title, `${path} needs a default export with a title`).toBeTruthy()
            expect(meta?.component, `${path} needs meta.component`).toBeTruthy()
            expect(stories.length).toBeGreaterThan(0)
        })

        for (const [name, story] of stories) {
            const tags: string[] = [...(meta.tags ?? []), ...(story.tags ?? [])]
            const run = tags.includes('!test') ? test.skip : test

            run(name, async () => {
                const args = { ...(meta.args ?? {}), ...(story.args ?? {}) }
                // Storybook renders meta.component only; a story-level override would pass here and break there.
                const component = meta.component
                const decorators = [...(story.decorators ?? []), ...(meta.decorators ?? [])]
                const html = await apply_decorators(await render_story(component, args), decorators, { args, parameters: { ...(meta.parameters ?? {}), ...(story.parameters ?? {}) } })

                const allow_empty = story.parameters?.rust?.allow_empty ?? meta.parameters?.rust?.allow_empty
                if (!allow_empty)
                    expect(html.trim(), 'story rendered nothing').not.toBe('')

                const canvas = await mount_story(html)
                const text = visible_text(canvas)
                for (const leak of LEAKS)
                    expect(text, `${leak} leaked into the rendered text`).not.toMatch(leak)

                const play = story.play ?? meta.play
                if (play && !tags.includes('browser')) {
                    await play({
                        canvasElement: canvas,
                        args,
                        initialArgs: args,
                        parameters: { ...(meta.parameters ?? {}), ...(story.parameters ?? {}) },
                        id: `${meta.title}/${name}`,
                        name,
                        title: meta.title,
                        tags,
                        step: async (_label: string, fn: () => Promise<void> | void) => { await fn() },
                        context: {},
                    })
                }
            })
        }
    })
}
