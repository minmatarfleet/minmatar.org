import { expect, within } from 'storybook/test'
import TribeGroupChip from '@components/blocks/TribeGroupChip.astro'
import { group_capitals, group_long, group_mining } from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/TribeGroupChip',
    component: TribeGroupChip,
    parameters: {
        docs: {
            description: {
                component: [
                    "A small chip showing which tribe group a fleet, post or event belongs to: the group's crest and name, linking to the group page (`/alliance/tribes/<tribe>/<group>/`).",
                    'It appears on fleet cards, news posts and event rows. Scenarios show the linked chip, the plain-span variant used inside rows that are already links, the tribe suffix and a long name cut with an ellipsis.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        size: { control: 'inline-radio', options: ['sm', 'md'] },
        show_tribe: { control: 'boolean', description: 'Append the tribe name.' },
        linked: { control: 'boolean', description: 'False renders a span instead of a link.' },
        max_width: { control: 'text', description: 'CSS max-width where the name is cut.' },
    },
    args: { group: group_capitals, size: 'md', show_tribe: false, linked: true },
}

export const Linked = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: /Capitals/ })
        await expect(link.getAttribute('href')).toContain('/alliance/tribes/1/3/')
        await expect(link).toHaveAttribute('title', 'Capitals · Warfare')
    },
}

export const WithTribeName = {
    args: { group: group_mining, show_tribe: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link.textContent).toContain('Mining')
        await expect(link.textContent).toContain('Supply')
    },
}

export const InsideLinkedRow = {
    args: { linked: false, size: 'sm' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).queryByRole('link')).toBeNull()
        await expect(canvasElement.querySelector('span.tribe-group-chip--sm')).not.toBeNull()
    },
}

export const LongNameTruncated = {
    args: { group: group_long, show_tribe: true, max_width: '16rem' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link.getAttribute('style')).toContain('max-width: 16rem')
        await expect(link.textContent).toContain('Faction Warfare Frigate Skirmishers of Amamake')
    },
}
