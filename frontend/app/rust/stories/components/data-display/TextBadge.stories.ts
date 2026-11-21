import { expect, within } from 'storybook/test'
import TextBadge from '@components/blocks/TextBadge.astro'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/TextBadge',
    component: TextBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'A heading with a short block of text under it, in a tight `Flexblock`. It carries the `badge` class and fills the width of its parent (`w-full`).',
                    'The title is an `<h4>` and the body is the default slot, so put text, `<small>` lines or a few inline elements there. Despite the name it is unrelated to `Badge` (picture plus title) and `NotificationBadge` (count bubble); it is the "label + explanation" pair, such as the in-demand and surplus notes on buyback.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'Heading, rendered as an `<h4>`.' },
    },
    args: {
        title: 'In demand',
        slots: { default: 'Rifters and Stabbers are needed for the next doctrine fleet.' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 4, name: 'In demand' })).toBeVisible()
        await expect(canvas.getByText(/Rifters and Stabbers/)).toBeVisible()
        const root = canvasElement.firstElementChild as HTMLElement
        await expect(root).toHaveClass('badge')
        await expect(root).toHaveClass('w-full')
    },
}

export const Surplus = {
    args: { title: 'Surplus', slots: { default: 'We hold more Caracal hulls than the next three fleets can use.' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByRole('heading', { name: 'Surplus' })).toBeVisible()
    },
}

export const RichBody = {
    args: {
        title: 'Formup',
        slots: { default: '<p>Undock at <strong>19:00 EVE</strong> in Amamake.</p><small class="text-muted">Bring a cyno alt.</small>' },
    },
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('19:00 EVE').tagName).toBe('STRONG')
        await expect(canvas.getByText('Bring a cyno alt.')).toBeVisible()
    },
}

export const LongText = {
    args: {
        title: 'Why this fleet is not on the schedule',
        slots: { default: 'The fleet commander is still waiting on a corp approval, and the formup system has not been confirmed with the logistics team yet, so the ping will go out as soon as both are settled.' },
    },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText(/still waiting on a corp approval/)).toBeVisible()
    },
}

export const TitleOnly = {
    args: { title: 'Nothing to report', slots: {} },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByRole('heading', { level: 4, name: 'Nothing to report' })).toBeVisible()
    },
}
