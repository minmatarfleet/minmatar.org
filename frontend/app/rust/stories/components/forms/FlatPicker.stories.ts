import { expect, userEvent, waitFor, within } from 'storybook/test'
import FlatPicker from '@components/blocks/FlatPicker.astro'

// FlatPicker initialises through `flatpickr(...)` in an Alpine `x-init`. The global comes from a CDN script
// that only Storybook's preview head loads, so the calendar itself exists only in the browser (stories that
// open it are tagged `browser`). Every story still asserts the server-rendered input and its serialised options.

const x_data = (input: HTMLElement) => input.getAttribute('x-data') ?? ''

export default {
    title: 'Components/Forms/FlatPicker',
    component: FlatPicker,
    parameters: {
        docs: {
            description: {
                component: [
                    'A text input that Alpine turns into a flatpickr date or time picker. `options` is a flatpickr options object, serialised into the `x-data` initialiser, so it must be plain JSON (no functions).',
                    'Other attributes (`id`, `name`, `type`, `x-model`, `required`) go to the input. An `icon` slot renders before it inside the `.input-group`.',
                    'Gotcha: `width` is accepted but not applied by the markup today. Pair the input with a `<label for>`; flatpickr needs its CDN script, which the site loads in the layout.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        options: { control: 'object', description: 'flatpickr options (`minDate`, `enableTime`, `noCalendar`, `dateFormat`, `mode`, ...).' },
        width: { control: 'text', description: 'Declared width, default `100%`. Currently not applied to the markup.' },
        id: { control: 'text', description: 'Passed to the input, pair it with a label.' },
        name: { control: 'text', description: 'Passed to the input.' },
        placeholder: { control: 'text', description: 'Passed to the input.' },
        required: { control: 'boolean', description: 'Passed to the input.' },
    },
    args: {
        id: 'timer_date',
        name: 'timer_date',
        options: { minDate: 'today' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = canvasElement.querySelector('input') as HTMLInputElement
        await expect(input).toHaveAttribute('type', 'text')
        await expect(input).toHaveAttribute('name', 'timer_date')
        await expect(input.closest('.input-group')).not.toBeNull()
        await expect(x_data(input)).toContain('flatpickr($el')
        await expect(x_data(input)).toContain('"minDate":"today"')
    },
}

export const OpensCalendar = {
    name: 'Opens the calendar on click',
    tags: ['browser'],
    args: { placeholder: 'Pick a timer date' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByPlaceholderText('Pick a timer date')
        await userEvent.click(input)
        await waitFor(() => expect(document.querySelector('.flatpickr-calendar.open')).not.toBeNull())
        const first_day = document.querySelector('.flatpickr-calendar.open .flatpickr-day:not(.flatpickr-disabled)') as HTMLElement
        await userEvent.click(first_day)
        await waitFor(() => expect((input as HTMLInputElement).value).not.toBe(''))
    },
}

export const TimeOnly = {
    name: 'Time only (24 hour)',
    args: {
        id: 'timer_time',
        name: 'timer_time',
        options: { enableTime: true, noCalendar: true, dateFormat: 'H:i', time_24hr: true },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = canvasElement.querySelector('input') as HTMLInputElement
        await expect(input).toHaveAttribute('name', 'timer_time')
        await expect(x_data(input)).toContain('"noCalendar":true')
        await expect(x_data(input)).toContain('"dateFormat":"H:i"')
        await expect(x_data(input)).toContain('"time_24hr":true')
    },
}

export const DateRange = {
    name: 'Date range',
    args: {
        id: 'fleet_window',
        name: 'fleet_window',
        placeholder: 'Start - end',
        options: { mode: 'range', dateFormat: 'Y-m-d' },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByPlaceholderText('Start - end')
        await expect(x_data(input)).toContain('"mode":"range"')
    },
}

export const Required = {
    args: { required: true, placeholder: 'Timer date' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const input = within(canvasElement).getByPlaceholderText('Timer date')
        await expect(input).toBeRequired()
    },
}

export const WithIconSlot = {
    name: 'With an icon slot',
    args: { slots: { icon: '<span class="rust-demo-box">Date</span>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const group = canvasElement.querySelector('.input-group') as HTMLElement
        await expect(within(group).getByText('Date')).toBeVisible()
        await expect(group.firstElementChild?.nextElementSibling?.tagName).toBe('INPUT')
    },
}
