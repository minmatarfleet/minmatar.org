import { expect, within } from 'storybook/test'
import Progress from '@components/blocks/Progress.astro'
import { select_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

const TONES = ['', 'success', 'warning', 'danger', 'disabled'] as const

export default {
    title: 'Components/Feedback/Progress',
    component: Progress,
    parameters: {
        docs: {
            description: {
                component: [
                    'A thin glowing `<progress>` bar. Every attribute is passed straight to the native element, so `value`, `max` and `class` work as in HTML.',
                    'The tone comes from a class on the element: none (highlight), `success`, `warning`, `danger` or `disabled`. Put the percentage as slot text so screen readers and non-CSS clients still get it; the bar animates open once on load.',
                    'Use `Progress` for a known amount (skill training, blueprint research, SRP budget). For an unknown wait use a loading state instead; omit `value` only if you want the browser\'s indeterminate bar.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        value: { control: { type: 'number', min: 0, max: 100 }, description: 'Current amount, between 0 and `max`.' },
        max: { control: 'number', description: 'Amount that counts as complete.' },
        class: select_control(TONES, 'Tone class: highlight (empty), `success`, `warning`, `danger` or `disabled`. Combine with layout utilities such as `w-full`.'),
    },
    args: {
        value: 60,
        max: 100,
        class: 'w-full',
        slots: { default: '60%' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const bar = within(canvasElement).getByRole('progressbar')
        await expect(bar.tagName).toBe('PROGRESS')
        await expect(bar).toHaveAttribute('value', '60')
        await expect(bar).toHaveAttribute('max', '100')
        await expect(bar).toHaveTextContent('60%')
        await expect(bar).toHaveClass('w-full')
    },
}

export const Complete = {
    args: { value: 100, class: 'w-full success', slots: { default: '100%' } },
    play: async ({ canvasElement }: Play) => {
        const bar = within(canvasElement).getByRole('progressbar')
        await expect(bar).toHaveClass('success')
        await expect(bar).toHaveAttribute('value', '100')
    },
}

export const Warning = {
    args: { value: 85, class: 'w-full warning', slots: { default: '85% of SRP budget used' } },
    play: async ({ canvasElement }: Play) => {
        const bar = within(canvasElement).getByRole('progressbar')
        await expect(bar).toHaveClass('warning')
        await expect(bar).toHaveTextContent('85% of SRP budget used')
    },
}

export const Danger = {
    args: { value: 97, class: 'w-full danger', slots: { default: '97%' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByRole('progressbar')).toHaveClass('danger')
    },
}

export const Disabled = {
    args: { value: 30, class: 'w-full disabled', slots: { default: '30%' } },
    play: async ({ canvasElement }: Play) => {
        const bar = within(canvasElement).getByRole('progressbar')
        await expect(bar).toHaveClass('disabled')
        await expect(bar).toHaveAttribute('value', '30')
    },
}

export const CustomMax = {
    name: 'Custom max (3 of 5 fleets)',
    args: { value: 3, max: 5, class: 'w-full success', slots: { default: '3 / 5 fleets' } },
    play: async ({ canvasElement }: Play) => {
        const bar = within(canvasElement).getByRole('progressbar')
        await expect(bar).toHaveAttribute('max', '5')
        await expect(bar).toHaveAttribute('value', '3')
    },
}

export const Empty = {
    args: { value: 0, slots: { default: '0%' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByRole('progressbar')).toHaveAttribute('value', '0')
    },
}
