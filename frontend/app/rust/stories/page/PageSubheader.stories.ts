import { expect, within } from 'storybook/test'
import PageSubheader from '@components/page/PageSubheader.astro'
import Badge from '@components/blocks/Badge.astro'

export default {
    title: 'Page/PageSubheader',
    component: PageSubheader,
    parameters: {
        docs: {
            description: {
                component: [
                    'The line of context under a page title: a short description, badges, a fleet time. It is a `FlexInline` with the `subheader-content` class, so the header layout can find it.',
                    'The component tries to add `is-empty` when the slot is empty so the header can collapse the row, but it compares the rendered slot with `null` while Astro returns an empty string, so the class is not applied today. Extra attributes and `class` are applied to the wrapper.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        is_empty: { control: 'boolean', description: 'Accepted for backwards compatibility; emptiness is detected from the slot.' },
    },
    args: {
        is_empty: false,
        slots: { default: 'Alliance fleet, Rifter Armada doctrine. Undock 19:00 EVE time out of Amamake.' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = canvasElement.querySelector('.subheader-content')
        await expect(root).not.toBeNull()
        await expect(root).not.toHaveClass('is-empty')
        await expect(within(canvasElement).getByText(/Undock 19:00 EVE time/)).toBeVisible()
    },
}

export const WithBadges = {
    args: {
        slots: {
            default: [
                'Fleet 92221',
                { component: Badge, props: { color: 'alliance-blue' }, slots: { default: 'Strategic' } },
                { component: Badge, props: { color: 'green' }, slots: { default: 'Open to alliance' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Strategic')).toBeVisible()
        await expect(canvas.getByText('Open to alliance')).toBeVisible()
        await expect(canvasElement.querySelector('.subheader-content')).toHaveTextContent('Fleet 92221')
    },
}

export const Empty = {
    args: { slots: {} },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // Astro.slots.render returns '' (not null) for an empty slot, so `is-empty` is never applied today.
        await expect(canvasElement.querySelector('.subheader-content')?.textContent?.trim()).toBe('')
    },
}

export const WithClassAndAttributes = {
    args: { class: 'text-muted', 'data-testid': 'fleet-subheader', slots: { default: 'Doctrine: Muninn Fleet' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const root = within(canvasElement).getByTestId('fleet-subheader')
        await expect(root).toHaveClass('subheader-content')
        await expect(root).toHaveClass('text-muted')
    },
}

export const LongContent = {
    args: {
        slots: {
            default: 'Defence of the Amamake freeport against the Amarr Navy push. Bring a logistics alt, a cyno alt if you have one, and read the doctrine page before undock. SRP is covered for everything on the doctrine list.',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/SRP is covered/)).toBeVisible()
    },
}
