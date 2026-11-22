import { expect, userEvent, within } from 'storybook/test'
import Input from '@components/blocks/Input.astro'
import FlagIcon from '@components/icons/FlagIcon.astro'
import { radio_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }


export default {
    title: 'Components/Forms/Input',
    component: Input,
    parameters: {
        docs: {
            description: {
                component: [
                    'The site text field: a bordered, blurred-glass `<input>` inside an `.input-group`. Every other attribute (`type`, `name`, `placeholder`, `required`, `x-model`, `hx-*`) passes to the `<input>`. Pair it with a `<label for>`; the component does not render one.',
                    'Put an icon in the `icon` slot and the input pads itself to clear it. Pass `prefix` for fixed text before the value (a page address, a unit). Wrap it in `InputError` to show a validation marker. Use `Textarea` for multi-line text and `Select` for a fixed list.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        width: { control: 'text', description: 'Max width of the field as a CSS length. Defaults to 100%.' },
        size: radio_control(['lg', 'sm'] as const, '`sm` for filter bars and table rows.'),
        prefix: { control: 'text', description: 'Fixed text before the value, such as a URL path. One shell is drawn around the text and the input.' },
        prefix_attributes: { control: 'object', description: 'Attributes for the prefix `<span>` (`x-show`, `id`).' },
        type: { control: 'select', options: ['text', 'search', 'number', 'date', 'time', 'password'], description: 'Passed to the `<input>`.' },
        name: { control: 'text', description: 'Passed to the `<input>`.' },
        id: { control: 'text', description: 'Passed to the `<input>`; match it with a label `for`.' },
        placeholder: { control: 'text', description: 'Passed to the `<input>`.' },
        value: { control: 'text', description: 'Initial value.' },
        required: { control: 'boolean', description: 'Passed to the `<input>`.' },
        disabled: { control: 'boolean', description: 'Passed to the `<input>`.' },
        readonly: { control: 'boolean', description: 'Passed to the `<input>`.' },
    },
    args: {
        width: '100%',
        size: 'lg',
        type: 'text',
        id: 'pilot-name',
        name: 'pilot_name',
        placeholder: 'Pilot name',
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('Pilot name')
        await expect(input).toHaveAttribute('data-size', 'lg')
        await expect(input).toHaveAttribute('type', 'text')
        await expect(canvasElement.querySelector('.input-group')).not.toBeNull()
    },
}

export const AcceptsText = {
    args: { placeholder: 'Search pilots' , type: 'search', id: 'pilot-search', name: 'q' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('Search pilots') as HTMLInputElement
        await userEvent.type(input, "Kel'dar Atram")
        await expect(input).toHaveValue("Kel'dar Atram")
    },
}

export const Named = {
    args: { id: 'fleet-name', name: 'fleet_name', placeholder: 'Rifter roam' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('Rifter roam')
        await expect(input).toHaveAttribute('id', 'fleet-name')
        await expect(input).toHaveAttribute('name', 'fleet_name')
    },
}

export const Required = {
    args: { required: true, id: 'srp-link', name: 'killmail', placeholder: 'zKillboard link' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('zKillboard link')
        await expect(input).toBeRequired()
    },
}

export const Disabled = {
    args: { disabled: true, value: 'Locked by FC', id: 'locked' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByDisplayValue('Locked by FC') as HTMLInputElement
        await expect(input).toBeDisabled()
        await userEvent.type(input, 'abc')
        await expect(input).toHaveValue('Locked by FC')
    },
}

export const ReadOnly = {
    args: { readonly: true, value: 'https://my.minmatar.org/fleets/92221/', id: 'share-link' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByDisplayValue(/92221/) as HTMLInputElement
        await expect(input).toHaveAttribute('readonly')
        await userEvent.type(input, 'abc')
        await expect(input).toHaveValue('https://my.minmatar.org/fleets/92221/')
    },
}

export const Small = {
    args: { size: 'sm', placeholder: 'Filter', id: 'filter' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByPlaceholderText('Filter')).toHaveAttribute('data-size', 'sm')
    },
}

export const WithIcon = {
    args: { placeholder: 'Flag a pilot', id: 'flag', slots: { icon: { component: FlagIcon } } },
    play: async ({ canvasElement }: Ctx) => {
        const group = canvasElement.querySelector('.input-group') as HTMLElement
        await expect(group.querySelector('svg')).not.toBeNull()
        await expect(within(group).getByPlaceholderText('Flag a pilot')).toBeVisible()
    },
}

export const WithPrefix = {
    args: { prefix: '/learning/', placeholder: 'page-address', id: 'page-address', name: 'slug' },
    play: async ({ canvasElement }: Ctx) => {
        const group = canvasElement.querySelector('.input-group') as HTMLElement
        await expect(group.classList.contains('input-group--prefixed')).toBe(true)
        await expect(group.querySelector('.input-prefix')).toHaveTextContent('/learning/')
        await expect(within(group).getByPlaceholderText('page-address')).toHaveAttribute('name', 'slug')
    },
}

export const PrefixKeepsTyping = {
    name: 'Prefix is not part of the value',
    args: { prefix: '/learning/', placeholder: 'page-address', id: 'page-address-2', name: 'slug' },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('page-address') as HTMLInputElement
        await userEvent.type(input, 'rifter-basics')
        await expect(input).toHaveValue('rifter-basics')
    },
}

export const NumberAndDate = {
    name: 'Number type',
    args: { type: 'number', placeholder: 'ISK per kill', id: 'isk', min: 0, step: 1000000 },
    play: async ({ canvasElement }: Ctx) => {
        const input = within(canvasElement).getByPlaceholderText('ISK per kill') as HTMLInputElement
        await userEvent.type(input, '25000000')
        await expect(input).toHaveValue(25000000)
        await expect(input).toHaveAttribute('step', '1000000')
    },
}

export const NarrowWidth = {
    args: { width: '12rem', placeholder: 'Ticker', id: 'ticker' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByPlaceholderText('Ticker')).toBeVisible()
    },
}

export const FocusRing = {
    name: 'Keyboard focus ring',
    tags: ['browser'], // asserts the computed style from the component's CSS
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const field = canvasElement.querySelector("input") as HTMLElement
        await expect(getComputedStyle(field).outlineStyle).toBe('none')
        field.focus()
        // Same double highlight outline as links (`a:focus-visible` in _global.scss).
        await expect(getComputedStyle(field).outlineStyle).toBe('double')
        await expect(getComputedStyle(field).outlineColor).not.toBe('rgba(0, 0, 0, 0)')
    },
}
