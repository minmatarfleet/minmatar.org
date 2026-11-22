import { expect, within, userEvent, waitFor } from 'storybook/test'
import FilterChip from '@components/blocks/FilterChip.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Navigation/FilterChip',
    component: FilterChip,
    parameters: {
        docs: {
            description: {
                component: [
                    'A pill-shaped toggle for filtering a list. As a `<button>` (client-side filter) it reports state with `aria-pressed`; with `href` it is a link to a filtered view and marks the current one with `aria-current="page"`.',
                    'With `type="radio"` or `type="checkbox"` it is a label around a hidden input, so a surrounding form (or an htmx `change` trigger) reads the choice; the checked chip takes the active look.',
                    '`tone` grades the chip in a brand colour (`red`, `green`, `blue`, `purple`; `yellow` is the default): the outline and text take the colour and the selected chip fills with it, white text on red, green, blue and purple, dark text on yellow. `count` adds a muted number after the label.',
                    '`removable` draws an applied tag (a label plus a × button) instead of a toggle: `remove_label` is the button\'s aria-label and `remove_attributes` carries its `x-on:click` or `hx-*`; `as="li"` makes it a list item.',
                    'For an Alpine filter, bind `x-bind:class` (`is-active`), `x-bind:aria-pressed` and `x-on:click` yourself; `active` is only the server-rendered starting state. Put chips in a `ChipGroup` so they scroll sideways with an edge fade instead of overflowing.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        active: { control: 'boolean', description: 'Server-rendered selected state: `is-active` class plus `aria-pressed` / `aria-current`.' },
        href: { control: 'text', description: 'Render a link to a filtered view instead of a toggle button.' },
        type: { control: 'inline-radio', options: [undefined, 'radio', 'checkbox'], description: 'Render a hidden radio or checkbox inside a label, for a filter that submits with a form or reloads on `change`.' },
        name: { control: 'text', description: 'Input mode: the input name.' },
        value: { control: 'text', description: 'Input mode: the input value.' },
        checked: { control: 'boolean', description: 'Input mode: the checked state; the checked chip takes the active look.' },
        input_attributes: { control: 'object', description: 'Input mode: attributes for the input (`x-model`, `hx-*`).' },
        tone: { control: 'inline-radio', options: ['yellow', 'red', 'green', 'blue', 'purple'], description: 'Brand colour grade for the outline, text and selected fill.' },
        count: { control: 'text', description: 'A muted number after the label.' },
        removable: { control: 'boolean', description: 'Render an applied tag with a × button instead of a toggle.' },
        remove_label: { control: 'text', description: 'Removable: aria-label of the × button.' },
        remove_attributes: { control: 'object', description: 'Removable: attributes for the × button (`x-on:click`, `hx-*`).' },
        as: { control: 'inline-radio', options: ['span', 'li'], description: 'Removable: the chip element.' },
        class: { control: 'text', description: 'Extra classes.' },
    },
    args: {
        active: false,
        slots: { default: 'Frigates' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Frigates' })
        await expect(chip).toHaveClass('filter-chip')
        await expect(chip).not.toHaveClass('is-active')
        await expect(chip).toHaveAttribute('aria-pressed', 'false')
        await expect(chip).toHaveAttribute('type', 'button')
    },
}

export const Active = {
    args: { active: true },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Frigates' })
        await expect(chip).toHaveClass('is-active')
        await expect(chip).toHaveAttribute('aria-pressed', 'true')
    },
}

export const AlpineToggle = {
    name: 'Alpine toggle',
    // Alpine state lives on the chip itself here; a real filter shares it on a parent (see ChipGroup).
    args: {
        'x-data': '{ on: false }',
        'x-on:click': 'on = !on',
        'x-bind:aria-pressed': "on ? 'true' : 'false'",
        slots: { default: 'Hide off-doctrine' },
    },
    tags: ['browser'],
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Hide off-doctrine' })
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'false'))
        await userEvent.click(chip)
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'true'))
        await userEvent.click(chip)
        await waitFor(() => expect(chip).toHaveAttribute('aria-pressed', 'false'))
    },
}

export const LinkChip = {
    name: 'Link to a filtered view',
    args: { href: '/fleets/history/?type=strategic', slots: { default: 'Strategic' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('link', { name: 'Strategic' })
        await expect(chip).toHaveAttribute('href', '/fleets/history/?type=strategic')
        await expect(chip).not.toHaveAttribute('aria-current')
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
    },
}

export const ActiveLinkChip = {
    name: 'Current link chip',
    args: { href: '/fleets/history/?type=strategic', active: true, slots: { default: 'Strategic' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('link', { name: 'Strategic' })
        await expect(chip).toHaveAttribute('aria-current', 'page')
        await expect(chip).toHaveClass('is-active')
    },
}

export const Passthrough = {
    name: 'Attributes pass through',
    args: { 'data-filter': 'frigate', class: 'my-chip' },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button')
        await expect(chip).toHaveAttribute('data-filter', 'frigate')
        await expect(chip).toHaveClass('filter-chip', 'my-chip')
    },
}

export const RadioChip = {
    name: 'Radio chip (form filter)',
    args: { type: 'radio', name: 'view', value: 'upcoming', checked: true, slots: { default: 'Upcoming' } },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Upcoming' })
        await expect(input).toBeChecked()
        await expect(input).toHaveAttribute('name', 'view')
        await expect(input).toHaveAttribute('value', 'upcoming')
        const label = input.closest('label')!
        await expect(label).toHaveClass('filter-chip', 'filter-chip--input')
        await expect(within(canvasElement).queryByRole('button')).toBeNull()
    },
}

export const CheckboxChip = {
    name: 'Checkbox chip',
    args: { type: 'checkbox', name: 'brackets', value: 'USTZ', slots: { default: 'USTZ' } },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByRole('checkbox', { name: 'USTZ' })
        await expect(input).not.toBeChecked()
        await userEvent.click(input)
        await expect(input).toBeChecked()
    },
}

export const InputAttributes = {
    name: 'Input attributes (x-model)',
    args: {
        type: 'radio',
        name: 'mode',
        value: 'rate',
        input_attributes: { 'x-model': 'mode', 'data-test': 'rate-input' },
        'data-chip': 'rate',
        slots: { default: 'Per m3' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Per m3' })
        await expect(input).toHaveAttribute('x-model', 'mode')
        await expect(input).toHaveAttribute('data-test', 'rate-input')
        // Everything else goes to the label, not the input.
        await expect(input.closest('label')).toHaveAttribute('data-chip', 'rate')
        await expect(input).not.toHaveAttribute('data-chip')
    },
}

export const ToneRed = {
    name: 'Tone: red, selected',
    args: { tone: 'red', active: true, slots: { default: 'Hostile' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Hostile' })
        await expect(chip).toHaveClass('filter-chip', 'filter-chip--red', 'is-active')
        await expect(chip).toHaveAttribute('aria-pressed', 'true')
    },
}

export const TonePurple = {
    name: 'Tone: purple, not selected',
    args: { tone: 'purple', slots: { default: 'Militia' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Militia' })
        await expect(chip).toHaveClass('filter-chip--purple')
        await expect(chip).not.toHaveClass('is-active')
    },
}

export const ToneYellowIsDefault = {
    name: 'Tone: yellow adds no class',
    args: { tone: 'yellow', slots: { default: 'Frigates' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: 'Frigates' })
        await expect(chip.className).not.toMatch(/filter-chip--/)
    },
}

export const ToneRadio = {
    name: 'Tone on a radio chip',
    args: { tone: 'green', type: 'radio', name: 'view', value: 'good', checked: true, slots: { default: 'Healthy' } },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByRole('radio', { name: 'Healthy' })
        await expect(input).toBeChecked()
        await expect(input.closest('label')).toHaveClass('filter-chip--green', 'filter-chip--input')
    },
}

export const WithCount = {
    name: 'With a count',
    args: { count: 12, slots: { default: 'Open' } },
    play: async ({ canvasElement }: Ctx) => {
        const chip = within(canvasElement).getByRole('button', { name: /Open/ })
        await expect(chip).toHaveTextContent('Open')
        await expect(chip.querySelector('.filter-chip__count')).toHaveTextContent('12')
    },
}

export const Removable = {
    name: 'Removable tag',
    // The click handler lives on the × button, exactly where the caller's own button had it.
    args: {
        removable: true,
        remove_label: 'Remove Amamake',
        remove_attributes: { 'x-data': '', 'data-hx-delete': '/tags/amamake' },
        slots: { default: 'Amamake' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const remove = within(canvasElement).getByRole('button', { name: 'Remove Amamake' })
        await expect(remove).toHaveAttribute('type', 'button')
        await expect(remove).toHaveAttribute('data-hx-delete', '/tags/amamake')
        const chip = remove.closest('.filter-chip')!
        await expect(chip).toHaveClass('filter-chip--removable')
        await expect(chip).toHaveTextContent('Amamake')
        await expect(chip).not.toHaveAttribute('aria-pressed')
    },
}

export const RemovableListItem = {
    name: 'Removable tag as a list item, with tone',
    args: { removable: true, as: 'li', tone: 'blue', remove_label: 'Remove Pulse', slots: { default: 'Pulse' } },
    play: async ({ canvasElement }: Ctx) => {
        const item = within(canvasElement).getByText('Pulse').closest('li')!
        await expect(item).toHaveClass('filter-chip', 'filter-chip--blue', 'filter-chip--removable')
        await expect(within(item).getAllByRole('button')).toHaveLength(1)
    },
}
