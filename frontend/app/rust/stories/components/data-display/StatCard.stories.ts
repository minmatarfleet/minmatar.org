import { expect, within } from 'storybook/test'
import StatCard from '@components/blocks/StatCard.astro'
import { radio_control } from '../../_controls'


export default {
    title: 'Components/Data display/StatCard',
    component: StatCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A big-number card: an uppercase label, the value in the heading font, and an optional hint line. Use it for tribe and fleet headline numbers; for a row of them lay the cards out with Grid.',
                    '`value` and `hint` also come as named slots for markup such as a tooltip span (see NumberNameTooltip). `coming_soon` swaps the value for a dashed placeholder, for metrics that are announced but not wired up yet; `coming_soon_label` changes its text.',
                    '`variant="compact"` is a smaller card for dense rows of stats. `variant="bar"` adds a thin progress bar under the value, filled to `bar_value` (0 to 1). `tone` colours the value and the bar.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        label: { control: 'text', description: 'Uppercase caption above the value.' },
        value: { control: 'text', description: 'The big number or text. Use the `value` slot for markup.' },
        hint: { control: 'text', description: 'Small line under the value. Use the `hint` slot for markup.' },
        coming_soon: { control: 'boolean', description: 'Dashed card with a "coming soon" label instead of the value.' },
        coming_soon_label: { control: 'text', description: 'Text of the placeholder; the translated "coming soon" when unset.' },
        variant: radio_control(['default', 'compact', 'bar'] as const, '`compact`: smaller card. `bar`: progress bar under the value.'),
        bar_value: { control: { type: 'range', min: 0, max: 1, step: 0.05 }, description: 'Bar fill from 0 to 1 (`variant: bar`).' },
        tone: radio_control(['fleet-red', 'green', 'alliance-blue', 'fleet-yellow'] as const, 'Colour of the value and the bar; highlight when unset.'),
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


export const Compact = {
    args: { variant: 'compact', label: 'Pilots flying', value: '1,168', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(card).toHaveClass('stat-card', 'stat-card--compact')
        await expect(within(card).getByText('1,168')).toBeVisible()
    },
}

export const WithBar = {
    name: 'Bar (progress)',
    args: { variant: 'bar', label: 'Fleet fill', value: '38 / 50', bar_value: 0.76, tone: 'green', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(card).toHaveClass('stat-card--bar')
        await expect(card.getAttribute('style')).toContain('--stat-tone: var(--green)')
        const bar = within(card).getByRole('meter', { name: 'Fleet fill' })
        await expect(bar).toHaveAttribute('aria-valuenow', '76')
        await expect(bar.getAttribute('style')).toContain('--stat-bar: 76%')
    },
}

export const BarClamped = {
    name: 'Bar value is clamped to 0-1',
    args: { variant: 'bar', label: 'Over target', value: '120%', bar_value: 1.2, tone: 'fleet-red', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('meter')).toHaveAttribute('aria-valuenow', '100')
    },
}

export const Toned = {
    args: { tone: 'alliance-blue', label: 'SRP paid', value: '12.4B' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('article')
        await expect(card.getAttribute('style')).toContain('--stat-tone: var(--alliance-blue)')
        await expect(card.querySelector('.stat-card__bar')).toBeNull()
    },
}

export const ComingSoonLabel = {
    name: 'Coming soon with a custom label',
    args: { label: 'Tournament wins', coming_soon: true, coming_soon_label: 'After the next tournament', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('After the next tournament')).toBeVisible()
    },
}
