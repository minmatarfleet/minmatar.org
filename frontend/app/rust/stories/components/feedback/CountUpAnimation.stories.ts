import { expect } from 'storybook/test'
import CountUpAnimation from '@components/blocks/CountUpAnimation.astro'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Feedback/CountUpAnimation',
    component: CountUpAnimation,
    parameters: {
        docs: {
            description: {
                component: [
                    'A number that counts up from 0 to `target` with an ease-out curve when it appears (Alpine + `requestAnimationFrame`). Use it for headline stats such as "pilots flew this month"; use a plain number anywhere the value matters to read immediately or for crawlers.',
                    'The server only renders `0`, and the final value is written with `toLocaleString()` in the viewer\'s locale, so large numbers get thousands separators. Extra attributes (`class`, `id`) go to the element, which is a `<span>` unless `element` says otherwise.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        target: { control: 'number', description: 'The number to count up to.' },
        duration: { control: 'number', description: 'Animation length in milliseconds.' },
        element: { control: 'text', description: 'Tag name to render (`span`, `strong`, `h2`, ...).' },
        class: { control: 'text', description: 'Classes for the element, such as a type-scale utility.' },
    },
    args: {
        target: 12840,
        duration: 3000,
        element: 'span',
    },
}

const counter = (canvasElement: HTMLElement) => canvasElement.querySelector('[x-data]') as HTMLElement

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const el = counter(canvasElement)
        await expect(el.tagName).toBe('SPAN')
        await expect(el.getAttribute('x-data')).toContain('target: 12840')
        await expect(el.getAttribute('x-data')).toContain('duration: 3000')
    },
}

export const Fast = {
    args: { target: 540, duration: 300 },
    tags: ['browser'],
    play: async ({ canvasElement }: Play) => {
        const el = counter(canvasElement)
        await expect(el.getAttribute('x-data')).toContain('duration: 300')
        // requestAnimationFrame needs a real browser: wait for the final value.
        await new Promise((resolve) => setTimeout(resolve, 900))
        await expect(el.textContent?.trim()).toBe((540).toLocaleString())
    },
}

export const Heading = {
    args: { element: 'h2', target: 2112, class: 'text-highlight' },
    play: async ({ canvasElement }: Play) => {
        const el = counter(canvasElement)
        await expect(el.tagName).toBe('H2')
        await expect(el).toHaveClass('text-highlight')
    },
}

export const Strong = {
    args: { element: 'strong', target: 99, duration: 1500 },
    play: async ({ canvasElement }: Play) => {
        await expect(counter(canvasElement).tagName).toBe('STRONG')
    },
}

export const LargeNumber = {
    args: { target: 1250000000, duration: 3000 },
    play: async ({ canvasElement }: Play) => {
        await expect(counter(canvasElement).getAttribute('x-data')).toContain('target: 1250000000')
    },
}
