import { expect, within } from 'storybook/test'
import Marquee from '@components/blocks/Marquee.astro'

const pilots = ['Kel\'dar Atram', 'Rattini Pilot', 'Fleet 94 FC', 'Hek Roamer', 'Amamake Defender']
    .map((name) => `<strong>${name}</strong>`).join('')

export default {
    title: 'Components/Data display/Marquee',
    component: Marquee,
    parameters: {
        docs: {
            description: {
                component: 'A horizontally scrolling ticker with faded edges. The slot content is rendered twice (with a rule between the copies) and animated by half its width, so the loop is seamless; Alpine measures the width and sets the duration (30 px per second). Use it for decorative strips such as recent pilots or headlines, never for essential information: it keeps moving and cannot be paused.',
            },
        },
    },
    argTypes: {
        separator_width: { control: 'text', description: 'Width of the rule between the two copies of the content.' },
    },
    args: { separator_width: '450px', slots: { default: pilots } },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const container = canvasElement.querySelector('.marquee-container') as HTMLElement
        await expect(container).toBeTruthy()
        // The slot is duplicated for the seamless loop.
        await expect(within(container).getAllByText("Kel'dar Atram")).toHaveLength(2)
        await expect(container.querySelectorAll('hr')).toHaveLength(2)
    },
}

export const NarrowSeparator = {
    name: 'Narrow separator',
    args: { separator_width: '120px' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const separators = Array.from(canvasElement.querySelectorAll('hr')).map((hr) => (hr.parentElement as HTMLElement).getAttribute('style'))
        await expect(separators.some((s) => s?.includes('120px'))).toBe(true)
    },
}

export const Headlines = {
    args: { slots: { default: '<strong>Fleet 94 forms 20:00 EVE</strong><strong>SRP payouts closed for October</strong><strong>New doctrine: Cormorant Navy Issue</strong>' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByText('SRP payouts closed for October')).toHaveLength(2)
    },
}

export const DurationFromWidth = {
    name: 'Duration set from width (browser)',
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const content = canvasElement.querySelector('.marquee-content') as HTMLElement
        // Alpine sets --duration after measuring; needs real layout.
        await new Promise((r) => setTimeout(r, 200))
        await expect(parseFloat(content.style.getPropertyValue('--duration'))).toBeGreaterThan(0)
    },
}
