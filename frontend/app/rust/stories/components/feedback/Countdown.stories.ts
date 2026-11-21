import { expect, within } from 'storybook/test'
import Countdown from '@components/blocks/Countdown.astro'

type Play = { canvasElement: HTMLElement }

// Fixed dates keep the render deterministic: one far in the past, one far in the future.
const PAST = '2020-01-01T19:00:00Z'
const FUTURE = '2099-01-01T19:00:00Z'

export default {
    title: 'Components/Feedback/Countdown',
    component: Countdown,
    parameters: {
        docs: {
            description: {
                component: [
                    'A ticking `HH : MM : SS` timer to an EVE (UTC) time, such as fleet formup. The server renders the first value and an Alpine `setInterval` updates it every second until the element leaves the DOM.',
                    'Once the date has passed the clock keeps counting up and gains the `expired` class (red) unless `expired_class` is off. Passing `expired_text` switches an expired timer to that word in the heading font (`expired-text`).',
                    '`id` and `tag` build the element id, so give each countdown on a page its own `id`. Use `StatusText` for a state word with no clock, and `LocalTime` for a clock time rather than a duration.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        id: { control: 'number', description: 'Unique number for this countdown; part of the element id.' },
        tag: { control: 'text', description: 'Prefix of the element id (`<tag>-<id>-<timestamp>`).' },
        date: { control: 'text', description: 'Target time, as an ISO string or a Date. Use UTC (`Z`).' },
        expired_text: { control: 'text', description: 'Word shown instead of the clock when the date has passed.' },
        expired_class: { control: 'boolean', description: 'Add the red `expired` class once the date has passed.' },
        big_font: { control: 'boolean', description: 'Use the larger `--step-4` size, for a page hero.' },
    },
    args: {
        id: 1,
        tag: 'countdown',
        date: FUTURE,
        expired_class: true,
        big_font: false,
    },
}

const timer = (canvasElement: HTMLElement) => canvasElement.querySelector('p.countdown') as HTMLElement

export const Default = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    play: async ({ canvasElement }: Play) => {
        const el = timer(canvasElement)
        await expect(el).toBeVisible()
        await expect(el.textContent?.trim()).toMatch(/^\d{2,} : \d{2} : \d{2}$/)
        await expect(el).not.toHaveClass('expired')
        await expect(el.id).toMatch(/^countdown-1-\d+$/)
        // The script Alpine runs counts down to this exact date.
        await expect(el.getAttribute('x-data')).toContain(`const date = '${FUTURE}'`)
    },
}

export const Expired = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    args: { date: PAST, id: 2 },
    play: async ({ canvasElement }: Play) => {
        const el = timer(canvasElement)
        await expect(el).toHaveClass('expired')
        await expect(el).not.toHaveClass('expired-text')
    },
}

export const ExpiredNotHighlighted = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    name: 'Expired without red (expired_class off)',
    args: { date: PAST, id: 3, expired_class: false },
    play: async ({ canvasElement }: Play) => {
        await expect(timer(canvasElement)).not.toHaveClass('expired')
    },
}

export const ExpiredText = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    args: { date: PAST, id: 4, expired_text: 'Fleet undocked' },
    play: async ({ canvasElement }: Play) => {
        const el = timer(canvasElement)
        await expect(el).toHaveClass('expired-text')
        await expect(el.getAttribute('x-data')).toContain("expired_text = 'Fleet undocked'")
    },
}

export const BigFont = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    args: { big_font: true, id: 5 },
    play: async ({ canvasElement }: Play) => {
        await expect(timer(canvasElement)).toHaveClass('big-font')
    },
}

export const CustomTag = {
    tags: ['browser'], // needs the global `pad()` from /js/countdown.js in preview-head
    args: { tag: 'formup', id: 6 },
    play: async ({ canvasElement }: Play) => {
        await expect(timer(canvasElement).id).toMatch(/^formup-6-\d+$/)
    },
}
