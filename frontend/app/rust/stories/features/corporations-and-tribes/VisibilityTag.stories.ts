import { expect, within } from 'storybook/test'
import VisibilityTag from '@components/blocks/tribes/VisibilityTag.astro'
import { radio_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Features/Corporations and tribes/VisibilityTag',
    component: VisibilityTag,
    parameters: {
        docs: {
            description: {
                component: [
                    'Who can see a tribe group item: a lock and "Members only" in yellow, or a globe and "Open to the alliance" in neutral. It is an outline `Tag` with an icon, so it sits beside other tags without competing.',
                    'Only group fleets and posts carry visibility; alliance-wide items never show it. `size="sm"` is for dense lists such as the fleet history table; `md` is for headers and cards. The label comes from i18n.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        visibility: radio_control(['members_only', 'open'] as const, '`members_only` is the yellow lock; `open` is the neutral globe.'),
        size: radio_control(['sm', 'md'] as const, '`sm` for dense rows, `md` otherwise.'),
    },
    args: {
        visibility: 'members_only',
        size: 'md',
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const tag = within(canvasElement).getByText('Members only')
        await expect(tag).toHaveClass('tag--outline')
        await expect(tag).toHaveClass('visibility-tag--md')
        await expect(tag.querySelector('svg')).not.toBeNull()
        await expect(tag.getAttribute('style')).toContain('var(--fleet-yellow)')
    },
}

export const Open = {
    args: { visibility: 'open' },
    play: async ({ canvasElement }: Play) => {
        const tag = within(canvasElement).getByText('Open to the alliance')
        await expect(tag.querySelector('svg')).not.toBeNull()
        // No colour requested: neutral outline.
        await expect(tag.getAttribute('style')).toContain('--outline_color: var(--highlight)')
        await expect(within(canvasElement).queryByText('Members only')).toBeNull()
    },
}

export const SmallMembersOnly = {
    args: { size: 'sm' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Members only')).toHaveClass('visibility-tag--sm')
    },
}

export const SmallOpen = {
    args: { visibility: 'open', size: 'sm' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Open to the alliance')).toHaveClass('visibility-tag--sm')
    },
}

export const PassThroughAttributes = {
    args: { class: 'ml-auto', title: 'Only Rattini Tribe members can see this fleet' },
    play: async ({ canvasElement }: Play) => {
        const tag = within(canvasElement).getByTitle('Only Rattini Tribe members can see this fleet')
        await expect(tag).toHaveClass('ml-auto')
        await expect(tag).toHaveClass('visibility-tag')
    },
}
