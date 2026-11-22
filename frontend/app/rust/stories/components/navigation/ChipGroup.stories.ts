import { expect, within, userEvent, waitFor } from 'storybook/test'
import ChipGroup from '@components/blocks/ChipGroup.astro'
import FilterChip from '@components/blocks/FilterChip.astro'

type Ctx = { canvasElement: HTMLElement }

const DOCTRINES = ['All doctrines', 'Rifter', 'Stabber', 'Hurricane', 'Muninn', 'Scimitar', 'Huginn', 'Sabre', 'Claymore']

export default {
    title: 'Components/Navigation/ChipGroup',
    component: ChipGroup,
    parameters: {
        docs: {
            description: {
                component: [
                    'A labelled row of `FilterChip`s (`role="group"`). By default it stays on one line and scrolls sideways with an edge fade (`XFadeScroll`), which suits filters on phones; `wrap` lets chips wrap onto several lines instead; `scroll_below="48rem"` wraps them on wide screens and scrolls them in one line below that width.',
                    'Always pass `aria_label` so screen readers announce what the chips filter. The group only lays chips out: the filtering state lives on the chips (Alpine or links).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        aria_label: { control: 'text', description: 'Accessible name of the group (what the chips filter).' },
        wrap: { control: 'boolean', description: 'Wrap onto several lines instead of one scrolling line.' },
        variant: { control: 'radio', options: ['default', 'segmented', 'grid'], description: '`segmented` joins the chips into one bordered control (mixed case, yellow-tinted selected segment); `grid` lays link chips out as icon cards.' },
        selected_fill: { control: 'boolean', description: 'Segmented only: the selected segment fills solid yellow instead of the tint with an underline.' },
        scroll_below: { control: 'text', description: 'A width such as `48rem`: chips wrap at and above it and scroll in one line below it.' },
        class: { control: 'text', description: 'Extra classes on the chip row.' },
    },
    args: {
        aria_label: 'Doctrine',
        wrap: false,
        slots: { default: chips(DOCTRINES) },
    },
}

// A function declaration, so it hoists above the meta that uses it (the library test reads the first `component:` in the file).
function chips(labels: string[], active = 0) {
    return labels.map((label, index) => ({
        component: FilterChip,
        props: { active: index === active },
        slots: { default: label },
    }))
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const group = canvas.getByRole('group', { name: 'Doctrine' })
        await expect(group).toHaveClass('chip-group')
        await expect(group).not.toHaveClass('chip-group--wrap')
        await expect(within(group).getAllByRole('button')).toHaveLength(DOCTRINES.length)
        await expect(within(group).getByRole('button', { name: 'All doctrines' })).toHaveAttribute('aria-pressed', 'true')
    },
}

export const Wrapping = {
    args: { wrap: true },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group', { name: 'Doctrine' })
        await expect(group).toHaveClass('chip-group--wrap')
        await expect(within(group).getAllByRole('button')).toHaveLength(DOCTRINES.length)
    },
}

export const FewChips = {
    name: 'Few chips',
    args: {
        aria_label: 'Fleet type',
        slots: { default: chips(['All', 'Strategic', 'Training'], 1) },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect(canvas.getByRole('group', { name: 'Fleet type' })).toBeVisible())
        await expect(canvas.getByRole('button', { name: 'Strategic' })).toHaveAttribute('aria-pressed', 'true')
        await expect(canvas.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
    },
}

export const NarrowContainer = {
    name: 'Scrolls in a narrow container',
    args: { slots: { default: chips(DOCTRINES) } },
    play: async ({ canvasElement }: Ctx) => {
        // The scroller (XFadeScroll) wraps the group when it does not wrap.
        const group = within(canvasElement).getByRole('group', { name: 'Doctrine' })
        await expect(group.parentElement).not.toBe(canvasElement)
        await expect(within(group).getAllByRole('button').length).toBeGreaterThan(5)
    },
}

export const LinkChips = {
    name: 'Link chips',
    args: {
        aria_label: 'Corporation',
        slots: {
            default: [
                { component: FilterChip, props: { href: '/alliance/corporations/', active: true }, slots: { default: 'All' } },
                { component: FilterChip, props: { href: '/alliance/corporations/a-rat/' }, slots: { default: 'A-RAT' } },
                { component: FilterChip, props: { href: '/alliance/corporations/fosfo/' }, slots: { default: 'FOSFO' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('link')).toHaveLength(3)
        await expect(canvas.getByRole('link', { name: 'All' })).toHaveAttribute('aria-current', 'page')
    },
}

export const Unlabelled = {
    name: 'Without aria_label',
    args: { aria_label: undefined, slots: { default: chips(['All', 'Mine']) } },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group')
        await expect(group).not.toHaveAttribute('aria-label')
    },
}

export const AlpineFilter = {
    name: 'Alpine filter',
    // Alpine state is shared on the group; the toggle assertions need a real browser.
    tags: ['browser'],
    args: {
        aria_label: 'Ship class',
        wrap: true,
        'x-data': "{ category: 'all' }",
        slots: {
            default: ['all:All', 'frigate:Frigates', 'cruiser:Cruisers', 'logi:Logistics'].map((entry) => {
                const [id, label] = entry.split(':')
                return {
                    component: FilterChip,
                    props: {
                        'x-on:click': `category = '${id}'`,
                        'x-bind:aria-pressed': `category === '${id}' ? 'true' : 'false'`,
                    },
                    slots: { default: label },
                }
            }),
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group', { name: 'Ship class' })
        const all = within(group).getByRole('button', { name: 'All' })
        const cruisers = within(group).getByRole('button', { name: 'Cruisers' })
        await waitFor(() => expect(all).toHaveAttribute('aria-pressed', 'true'))
        await expect(cruisers).toHaveAttribute('aria-pressed', 'false')
        await userEvent.click(cruisers)
        await waitFor(() => expect(cruisers).toHaveAttribute('aria-pressed', 'true'))
        await expect(all).toHaveAttribute('aria-pressed', 'false')
    },
}

export const WrapsOnDesktopScrollsOnPhone = {
    name: 'Wraps on desktop, scrolls on phone',
    args: { scroll_below: '48rem' },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group', { name: 'Doctrine' })
        await expect(group).toHaveClass('chip-group', 'chip-group--wrap')
        await expect(group).toHaveAttribute('data-scroll-below', '48rem')
        await expect(group.closest('.xfade-scroll')).toHaveAttribute('data-below', '48rem')
        await expect(within(group).getAllByRole('button')).toHaveLength(DOCTRINES.length)
    },
}

function radio_chips(values: string[], checked: string) {
    return values.map((label) => ({
        component: FilterChip,
        props: { type: 'radio', name: 'markup', value: label, checked: label === checked },
        slots: { default: label },
    }))
}

export const Segmented = {
    args: { variant: 'segmented', aria_label: 'Markup', slots: { default: radio_chips(['+10%', '+20%', 'Other', '0%'], '+10%') } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const group = canvas.getByRole('group', { name: 'Markup' })
        await expect(group).toHaveClass('chip-group--segmented')
        const radios = within(group).getAllByRole('radio')
        await expect(radios).toHaveLength(4)
        await expect(radios[0]).toBeChecked()
        await userEvent.click(canvas.getByText('Other'))
        await expect(canvas.getByRole('radio', { name: 'Other' })).toBeChecked()
        await expect(radios[0]).not.toBeChecked()
    },
}

export const SegmentedKeyboard = {
    name: 'Segmented, arrow keys',
    args: { variant: 'segmented', aria_label: 'Markup', slots: { default: radio_chips(['+10%', '+20%', 'Other'], '+10%') } },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const first = canvas.getByRole('radio', { name: '+10%' })
        first.focus()
        await userEvent.keyboard('{ArrowRight}')
        await expect(canvas.getByRole('radio', { name: '+20%' })).toBeChecked()
        await expect(first).not.toBeChecked()
    },
}

export const SegmentedFill = {
    name: 'Segmented, solid selected',
    args: { variant: 'segmented', selected_fill: true, aria_label: 'How sure', slots: { default: radio_chips(['Yes', 'Maybe', 'No'], 'Maybe') } },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group', { name: 'How sure' })
        await expect(group).toHaveClass('chip-group--segmented', 'chip-group--fill')
        await expect(within(group).getByRole('radio', { name: 'Maybe' })).toBeChecked()
    },
}

export const Grid = {
    name: 'Grid of link cards',
    args: {
        variant: 'grid',
        aria_label: 'Made from',
        slots: {
            default: ['Tritanium', 'Pyerite', 'Mexallon'].map((name) => ({
                component: FilterChip,
                props: { href: `/industry/products/${name.toLowerCase()}/` },
                slots: { default: name },
            })),
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const group = within(canvasElement).getByRole('group', { name: 'Made from' })
        await expect(group).toHaveClass('chip-group--grid')
        await expect(within(group).getAllByRole('link')).toHaveLength(3)
        await expect(within(group).getByRole('link', { name: 'Pyerite' })).toHaveAttribute('href', '/industry/products/pyerite/')
    },
}
