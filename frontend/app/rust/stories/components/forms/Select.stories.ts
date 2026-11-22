import { expect, userEvent, within } from 'storybook/test'
import Select from '@components/blocks/Select.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const options = (selected = '') => ['Rifter', 'Stabber', 'Hurricane', 'Muninn', 'Loki']
    .map(name => `<option value="${name.toLowerCase()}"${name.toLowerCase() === selected ? ' selected' : ''}>${name}</option>`)
    .join('')

export default {
    title: 'Components/Forms/Select',
    component: Select,
    parameters: {
        docs: {
            description: {
                component: [
                    'The site dropdown: a native `<select>` styled like `Input`, with a caret icon. Options go in the default slot as plain `<option>` HTML; every other attribute (`name`, `id`, `required`, `x-model`, `hx-*`) passes to the `<select>`.',
                    'It stays native so mobile pickers and keyboard search work. Mark the stored value with `selected` on its option. For two or three choices that should all be visible, use `RadioCheckInput`; for a type-ahead over many items use the page finders instead.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        width: { control: 'text', description: 'Max width of the select as a CSS length. Defaults to 100%.' },
        size: radio_control(['lg', 'sm'] as const, '`sm` for filter bars and table rows.'),
        name: { control: 'text', description: 'Passed to the `<select>`.' },
        id: { control: 'text', description: 'Passed to the `<select>`; match it with a label `for`.' },
        required: { control: 'boolean', description: 'Passed to the `<select>`.' },
        disabled: { control: 'boolean', description: 'Passed to the `<select>`.' },
        multiple: { control: 'boolean', description: 'Passed to the `<select>`.' },
    },
    args: {
        width: '100%',
        size: 'lg',
        name: 'hull',
        id: 'hull',
        'aria-label': 'Hull',
        slots: { default: options() },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' })
        await expect(select).toHaveAttribute('data-size', 'lg')
        await expect(within(select).getAllByRole('option')).toHaveLength(5)
        await expect(canvasElement.querySelector('svg')).not.toBeNull()
    },
}

// happy-dom does not apply `selected` on a non-first option to the select's value, so this play is browser-only.
export const SelectedValue = {
    tags: ['browser'],
    args: { slots: { default: options('hurricane') } },
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' }) as HTMLSelectElement
        await expect(within(select).getByRole('option', { name: 'Hurricane' })).toHaveAttribute('selected')
        await expect(select).toHaveValue('hurricane')
    },
}

export const ChangeSelection = {
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' })
        await userEvent.selectOptions(select, 'Muninn')
        await expect(select).toHaveValue('muninn')
    },
}

export const Small = {
    args: { size: 'sm', 'aria-label': 'Period', slots: { default: '<option>Last 7 days</option><option>Last 30 days</option><option>All time</option>' } },
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Period' })
        await expect(select).toHaveAttribute('data-size', 'sm')
        await expect(within(select).getAllByRole('option')).toHaveLength(3)
    },
}

export const Required = {
    args: {
        required: true,
        slots: { default: `<option value="" disabled selected>Choose a hull</option>${options()}` },
    },
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' })
        await expect(select).toBeRequired()
        await expect(select).toHaveValue('')
    },
}

export const Disabled = {
    args: { disabled: true, slots: { default: options('rifter') } },
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' })
        await expect(select).toBeDisabled()
        await expect(select).toHaveValue('rifter')
    },
}

export const Grouped = {
    args: {
        slots: {
            default: '<optgroup label="Frigates"><option>Rifter</option><option>Slasher</option></optgroup><optgroup label="Cruisers"><option>Stabber</option><option>Rupture</option></optgroup>',
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const select = within(canvasElement).getByRole('combobox', { name: 'Hull' })
        await expect(within(select).getAllByRole('group')).toHaveLength(2)
    },
}

export const NarrowWidth = {
    args: { width: '12rem' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('combobox')).toBeVisible()
    },
}

export const FocusRing = {
    name: 'Keyboard focus ring',
    tags: ['browser'], // asserts the computed style from the component's CSS
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const field = canvasElement.querySelector("select") as HTMLElement
        await expect(getComputedStyle(field).outlineStyle).toBe('none')
        field.focus()
        // Same double highlight outline as links (`a:focus-visible` in _global.scss).
        await expect(getComputedStyle(field).outlineStyle).toBe('double')
        await expect(getComputedStyle(field).outlineColor).not.toBe('rgba(0, 0, 0, 0)')
    },
}
