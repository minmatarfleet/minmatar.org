import { expect, within } from 'storybook/test'
import LocalTime from '@components/blocks/LocalTime.astro'
import { select_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Feedback/LocalTime',
    component: LocalTime,
    parameters: {
        docs: {
            description: {
                component: [
                    'Shows an EVE (UTC) time in the viewer\'s own timezone, coloured by the local hour: sleeptime reds, daytime yellows, evening greens and blues. The hour word ("Daytime") is the tippy tooltip, and is also printed when `show_label` is set.',
                    '`datetime` prints the full localized date and time; `time` prints HH:MM, prefixed with the weekday when the local day differs from the UTC day. Everything is computed client-side by Alpine, so the server output is only a "Localizing" placeholder.',
                    'Pass `eve_time` as a `Date`. The rendered value depends on the browser timezone, so tests assert the structure and attributes, not the clock text. Pair it with the plain EVE time, as fleet cards do.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        eve_time: { control: 'date', description: 'The time in UTC, as a Date.' },
        format: select_control(['datetime', 'time'] as const, '`datetime` full date; `time` hours and minutes (plus weekday on a different local day).'),
        show_label: { control: 'boolean', description: 'Also print the hour word ("Daytime", "Sleeptime") after the time.' },
    },
    args: {
        eve_time: new Date('2026-11-21T19:00:00Z'),
        format: 'time',
        show_label: false,
    },
}

const el = (canvasElement: HTMLElement) => canvasElement.querySelector('.local-time') as HTMLElement

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const time = el(canvasElement)
        await expect(time).toHaveClass('sentence-cap')
        await expect(time.getAttribute('x-data')).toContain('set_local_time')
        await expect(time.getAttribute('x-data')).toContain('set_time_class')
        await expect(time.getAttribute('x-bind:class')).toBe('time_class')
    },
}

export const DateAndTime = {
    args: { format: 'datetime' },
    play: async ({ canvasElement }: Play) => {
        await expect(el(canvasElement).getAttribute('x-data')).toContain("'datetime' === 'datetime'")
    },
}

export const WithLabel = {
    args: { show_label: true },
    play: async ({ canvasElement }: Play) => {
        const time = el(canvasElement)
        await expect(time.querySelector('[x-show="time_tooltip"]')).not.toBeNull()
    },
}

export const Sleeptime = {
    name: 'Sleeptime (03:00 UTC)',
    args: { eve_time: new Date('2026-11-21T03:00:00Z'), show_label: true },
    play: async ({ canvasElement }: Play) => {
        await expect(el(canvasElement).getAttribute('x-data')).toContain('set_time_class')
    },
}

export const CustomClass = {
    args: { class: 'text-muted' },
    play: async ({ canvasElement }: Play) => {
        await expect(el(canvasElement)).toHaveClass('text-muted')
    },
}
