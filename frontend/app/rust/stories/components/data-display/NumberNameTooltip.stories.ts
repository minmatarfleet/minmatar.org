import { expect, within } from 'storybook/test'
import NumberNameTooltip from '@components/blocks/NumberNameTooltip.astro'

// tippy moves the content out of the attribute once it attaches in the browser.
const tip = (el: Element) => el.getAttribute('data-tippy-content') ?? (el as any)._tippy?.props?.content ?? ''

export default {
    title: 'Components/Data display/NumberNameTooltip',
    component: NumberNameTooltip,
    parameters: {
        docs: {
            description: {
                component: 'A number with thousands separators whose tippy tooltip spells out the magnitude ("12.4 billion"), so large ISK amounts stay readable. Numbers below 1000 get an empty tooltip. The tooltip is attached by the site-wide tippy setup, and an approximation is prefixed with a "≈".',
            },
        },
    },
    argTypes: {
        number: { control: 'number', description: 'The number to show; its long name goes in the tooltip.' },
    },
    args: { number: 12_400_000_000 },
}

export const Billions = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = within(canvasElement).getByText('12,400,000,000')
        await expect(tip(el)).toBe('12.4 billion')
    },
}

export const Millions = {
    args: { number: 3_500_000 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = within(canvasElement).getByText('3,500,000')
        await expect(tip(el)).toBe('3.5 million')
    },
}

export const Approximate = {
    name: 'Approximate (prefixed with ≈)',
    args: { number: 1_234_567 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = within(canvasElement).getByText('1,234,567')
        await expect(tip(el)).toMatch(/^≈ 1\.2 million/)
    },
}

export const Thousands = {
    args: { number: 48_500 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(tip(within(canvasElement).getByText('48,500'))).toBe('48.5 thousand')
    },
}

export const BelowOneThousand = {
    name: 'Below 1000 (no tooltip text)',
    args: { number: 38 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const el = within(canvasElement).getByText('38')
        await expect(tip(el)).toBe('')
    },
}
