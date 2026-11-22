import { expect, within } from 'storybook/test'
import DebugTag from '@components/blocks/DebugTag.astro'
import { TAG_COLORS, select_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Data display/DebugTag',
    component: DebugTag,
    parameters: {
        docs: {
            description: {
                component: [
                    'A coloured strip that wraps an unexpected-error message in a partial, such as "no order found" when the API returned something the page cannot explain. Anything in the slot gets the padding, `--step--1` size and `--highlight` text; the colour fills behind it.',
                    'It is a developer-facing fallback, not a user message: a normal empty list should use `EmptyState`, and a failed fetch `ErrorRefetch`. Pass user-visible text through i18n. It never changes its own text, so the slot content must already be translated.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        color: select_control(TAG_COLORS, 'Background token behind the message.'),
    },
    args: {
        color: 'fleet-red',
        slots: { default: '<p>Unexpected error: this killmail has no matching fleet.</p>' },
    },
}

const strip = (canvasElement: HTMLElement) => canvasElement.querySelector('.debug-tag') as HTMLElement

export const Default = {
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText(/no matching fleet/)).toBeVisible()
        await expect(strip(canvasElement)).toBeVisible()
        await expect(strip(canvasElement).children).toHaveLength(1)
    },
}

export const Yellow = {
    args: { color: 'fleet-yellow', slots: { default: '<p>Warning: SRP program is closed.</p>' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Warning: SRP program is closed.')).toBeVisible()
    },
}

export const Blue = {
    args: { color: 'alliance-blue', slots: { default: '<p>Info: no order found for this id.</p>' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText(/no order found/)).toBeVisible()
    },
}

export const Green = {
    args: { color: 'green', slots: { default: '<span>Recovered after retry.</span>' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Recovered after retry.')).toBeVisible()
    },
}

export const SecurityColor = {
    args: { color: 'security-status-point-4', slots: { default: '<p>Lowsec route unavailable.</p>' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Lowsec route unavailable.')).toBeVisible()
    },
}

export const MultipleChildren = {
    args: { slots: { default: '<p>Error code 502</p><code>fleets/92221</code>' } },
    play: async ({ canvasElement }: Play) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Error code 502')).toBeVisible()
        await expect(canvas.getByText('fleets/92221').tagName).toBe('CODE')
        await expect(strip(canvasElement).children).toHaveLength(2)
    },
}

export const PassesAttributesThrough = {
    name: 'Extra attributes and classes reach the root',
    args: { class: 'ml-auto', 'data-testid': 'debug-root', slots: { default: '<span>trace 8f2c</span>' } },
    play: async ({ canvasElement }: Play) => {
        const root = within(canvasElement).getByTestId('debug-root')
        await expect(root).toHaveClass('debug-tag')
        await expect(root).toHaveClass('ml-auto')
    },
}
