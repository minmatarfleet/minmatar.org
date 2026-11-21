import { expect, within } from 'storybook/test'
import NotificationBadge from '@components/blocks/NotificationBadge.astro'
import { BADGE_COLORS, select_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/NotificationBadge',
    component: NotificationBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'A small square count bubble for a menu item or tab: unread alerts, open orders, pending applications. `number` is formatted with `format_number`, so large counts get separators.',
                    'The default slot overrides the number, for a short symbol such as `!` or a letter. The bubble is a fixed 1.2rem square, so keep content to one or two characters; use `Tag` for words. Text is `--highlight`, or `--fleet-red` on the yellow badge for contrast; `text_color` overrides it.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        number: { control: 'number', description: 'The count to show.' },
        color: select_control(BADGE_COLORS, 'Background token.'),
        text_color: { control: 'text', description: 'Override the text colour with any CSS value.' },
    },
    args: {
        number: 3,
        color: 'fleet-red',
    },
}

const style = (canvasElement: HTMLElement) => (canvasElement.querySelector('.badge') as HTMLElement).getAttribute('style') ?? ''

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const badge = within(canvasElement).getByText('3')
        await expect(badge).toHaveClass('badge')
        await expect(style(canvasElement)).toContain('--badge_background_color: var(--fleet-red)')
        await expect(style(canvasElement)).toContain('--badge_color: var(--highlight)')
    },
}

export const AllianceBlue = {
    args: { number: 12, color: 'alliance-blue' },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('12')).toBeVisible()
        await expect(style(canvasElement)).toContain('var(--alliance-blue)')
    },
}

export const MilitiaPurple = {
    args: { number: 4, color: 'militia-purple' },
    play: async ({ canvasElement }: Play) => {
        await expect(style(canvasElement)).toContain('var(--militia-purple)')
    },
}

export const Green = {
    args: { number: 7, color: 'green' },
    play: async ({ canvasElement }: Play) => {
        await expect(style(canvasElement)).toContain('--badge_background_color: var(--green)')
    },
}

export const Yellow = {
    name: 'Yellow (red text)',
    args: { number: 2, color: 'fleet-yellow' },
    play: async ({ canvasElement }: Play) => {
        await expect(style(canvasElement)).toContain('--badge_background_color: var(--fleet-yellow)')
        await expect(style(canvasElement)).toContain('--badge_color: var(--fleet-red)')
    },
}

export const CustomTextColor = {
    args: { text_color: 'var(--background)', color: 'green' },
    play: async ({ canvasElement }: Play) => {
        await expect(style(canvasElement)).toContain('--badge_color: var(--background)')
    },
}

export const LargeNumber = {
    name: 'Large number (compact)',
    args: { number: 1250 },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('1.3k')).toBeVisible()
    },
}

export const Zero = {
    args: { number: 0 },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('0')).toBeVisible()
    },
}

export const SlotOverride = {
    args: { slots: { default: '!' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('!')).toHaveClass('badge')
        await expect(within(canvasElement).queryByText('3')).toBeNull()
    },
}
