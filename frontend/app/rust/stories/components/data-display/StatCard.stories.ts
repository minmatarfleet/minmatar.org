import { expect, within } from 'storybook/test'
import StatCard from '@components/blocks/StatCard.astro'


export default {
    title: 'Components/Data display/StatCard',
    component: StatCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A big-number card: an uppercase label, the value in the heading font, and an optional hint line. Use it for tribe and fleet headline numbers; for a row of them lay the cards out with Grid.',
                    '`value` and `hint` also come as named slots for markup such as a tooltip span (see NumberNameTooltip). `coming_soon` swaps the value for a dashed placeholder, for metrics that are announced but not wired up yet.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        label: { control: 'text', description: 'Uppercase caption above the value.' },
        value: { control: 'text', description: 'The big number or text. Use the `value` slot for markup.' },
        hint: { control: 'text', description: 'Small line under the value. Use the `hint` slot for markup.' },
        coming_soon: { control: 'boolean', description: 'Dashed card with a "coming soon" label instead of the value.' },
    },
    args: {
        label: 'Fleets this month',
        value: '42',
        hint: '6 more than September',
        coming_soon: false,
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(card).toHaveClass('stat-card')
        await expect(within(card).getByText('Fleets this month')).toBeVisible()
        await expect(within(card).getByText('42')).toBeVisible()
        await expect(within(card).getByText('6 more than September')).toBeVisible()
    },
}

export const WithoutHint = {
    name: 'Without hint',
    args: { label: 'Pilots flying', value: 1168, hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(within(card).getByText('1168')).toBeVisible()
        await expect(card.querySelector('.stat-card__hint')).toBeNull()
    },
}

export const ComingSoon = {
    name: 'Coming soon',
    args: { label: 'Tournament wins', coming_soon: true, hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(card).toHaveClass('stat-card--soon')
        await expect(card.querySelector('.stat-card__value')).toBeNull()
        await expect(card.querySelector('.stat-card__soon')).toBeTruthy()
    },
}

export const SlottedValueAndHint = {
    name: 'Slotted value and hint',
    args: {
        label: 'SRP paid',
        value: undefined,
        hint: undefined,
        slots: {
            value: '<span data-tippy-content="About 12 billion ISK">12.4B</span>',
            hint: 'Across <strong>31</strong> approved claims',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        const value = within(card).getByText('12.4B')
        await expect(value.tagName).toBe('SPAN')
        await expect(card.querySelector('.stat-card__hint strong')?.textContent).toBe('31')
    },
}

export const LongLabel = {
    name: 'Long label and text value',
    args: { label: 'Most flown hull across all Strategic fleets', value: 'Cormorant Navy Issue', hint: 'Flown in 14 of 22 fleets' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('Cormorant Navy Issue')).toBeVisible()
    },
}

