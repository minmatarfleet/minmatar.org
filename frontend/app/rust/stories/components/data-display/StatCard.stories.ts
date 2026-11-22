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
                    '`variant="glass"` is the translucent campaign card: an `icon` slot beside the label and value, and the value may also be the default slot; tones `info`, `success`, `danger`, `minmatar`, `amarr` and `angel` alias the site colours. `variant="inline"` renders only the figure (value slot) with an optional `icon` slot, for a line of text such as the SRP approved/rejected totals. `variant="cell"` is one value-over-label cell of a divided stat bar (see CampaignStatBar); `title` is its tooltip.',
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
        variant: radio_control(['default', 'compact', 'bar', 'glass', 'inline', 'cell'] as const, '`compact`: smaller card. `bar`: progress bar under the value. `glass`: translucent card with an icon slot. `inline`: the figure alone. `cell`: value over label, for a divided bar.'),
        bar_value: { control: { type: 'range', min: 0, max: 1, step: 0.05 }, description: 'Bar fill from 0 to 1 (`variant: bar`).' },
        tone: radio_control(['fleet-red', 'green', 'alliance-blue', 'fleet-yellow', 'info', 'success', 'danger', 'minmatar', 'amarr', 'angel'] as const, 'Colour of the value and the bar; highlight when unset.'),
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

export const AsLink = {
    name: 'Link (whole card)',
    args: { href: '/alliance/reddit-review/', label: 'Reddit posts', value: 2, hint: 'Oldest 1 d · Rattini Tribe', tone: 'fleet-yellow' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = within(canvasElement).getByRole('link')
        await expect(card).toHaveClass('stat-card', 'stat-card--link')
        await expect(card).toHaveAttribute('href', '/alliance/reddit-review/')
        await expect(within(card).getByText('Reddit posts')).toBeVisible()
    },
}

export const ComingSoonLabel = {
    name: 'Coming soon with a custom label',
    args: { label: 'Tournament wins', coming_soon: true, coming_soon_label: 'After the next tournament', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('After the next tournament')).toBeVisible()
    },
}

export const Glass = {
    args: { variant: 'glass', label: 'ISK destroyed', value: '128.4b', tone: 'success', hint: undefined, slots: { icon: '<span data-testid="icon" aria-hidden="true">*</span>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = canvasElement.querySelector('.stat-card--glass') as HTMLElement
        await expect(card).toHaveClass('card', 'border', 'light-transparency')
        await expect(card.querySelector('b')?.getAttribute('style')).toContain('--stat-tone: var(--green)')
        await expect(within(card).getByText('ISK destroyed')).toBeVisible()
        await expect(within(card).getByText('128.4b')).toBeVisible()
        await expect(within(card).getByTestId('icon')).toBeInTheDocument()
    },
}

export const GlassFactionTone = {
    name: 'Glass, faction tone',
    args: { variant: 'glass', label: 'Amarr pilots', value: '212', tone: 'amarr', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const card = canvasElement.querySelector('.stat-card--glass') as HTMLElement
        await expect(card.querySelector('b')?.getAttribute('style')).toContain('--stat-tone: var(--fleet-yellow)')
        await expect(within(card).getByText('212')).toBeVisible()
    },
}

export const Inline = {
    args: { variant: 'inline', label: undefined, value: '4,210,000,000 ISK', hint: undefined, slots: { icon: '<span class="text-green" data-tippy-content="Approved, last 90 days">▲</span>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const inline = canvasElement.querySelector('.stat-card--inline') as HTMLElement
        await expect(inline.querySelector('h3')?.textContent).toContain('4,210,000,000 ISK')
        await expect(within(inline).getByText('▲')).toBeVisible()
        await expect(inline.querySelector('.stat-card__label')).toBeNull()
    },
}

export const Cell = {
    args: { variant: 'cell', label: 'Ships destroyed', value: '1,284', title: '1,284 ships', hint: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const cell = canvasElement.querySelector('.stat-card--cell') as HTMLElement
        await expect(cell).toHaveAttribute('title', '1,284 ships')
        await expect(within(cell).getByText('1,284')).toBeVisible()
        await expect(within(cell).getByText('Ships destroyed').tagName).toBe('SMALL')
    },
}
