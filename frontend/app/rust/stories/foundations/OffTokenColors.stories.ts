import { expect } from 'storybook/test'
import OffTokenColors from '../../components/foundations/OffTokenColors.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Foundations/Colours not yet tokens',
    component: OffTokenColors,
    parameters: {
        docs: {
            description: {
                component: 'Hex colours written straight into components and pages (`src/components`, `src/pages`, component stylesheets) instead of a token, with where each one is used. This is the backlog for the token layer: each colour should become a token, or switch to an existing one. The list is scanned from the source when the page renders.',
            },
        },
    },
    argTypes: {
        limit: { control: { type: 'number', min: 1 }, description: 'Show the most used N; all when unset.' },
    },
    args: {},
}

export const All = {
    play: async ({ canvasElement }: Ctx) => {
        const root = canvasElement.querySelector<HTMLElement>('.off-token')!
        const items = canvasElement.querySelectorAll('[data-color]')
        await expect(items.length).toBe(Number(root.dataset.total))
        for (const item of items)
            await expect((item as HTMLElement).dataset.color).toMatch(/^#[0-9a-f]{3,6}$/)
    },
}

export const MostUsed = {
    name: 'Most used ten',
    args: { limit: 10 },
    play: async ({ canvasElement }: Ctx) => {
        const counts = [...canvasElement.querySelectorAll('.count')].map((el) => parseInt(el.textContent!, 10))
        await expect(counts.length).toBeLessThanOrEqual(10)
        await expect([...counts].sort((a, b) => b - a)).toEqual(counts)
    },
}

export const FileLists = {
    name: 'Where each is used',
    args: { limit: 3 },
    play: async ({ canvasElement }: Ctx) => {
        for (const details of canvasElement.querySelectorAll('details'))
            await expect(details.querySelector('.files code')!.textContent).toMatch(/^src\//)
    },
}
