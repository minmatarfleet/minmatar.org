import { expect, within } from 'storybook/test'
import StatusText from '@components/blocks/StatusText.astro'
import { radio_control } from '../../_controls'

type Play = { canvasElement: HTMLElement }

export default {
    title: 'Components/Feedback/StatusText',
    component: StatusText,
    parameters: {
        docs: {
            description: {
                component: [
                    'A spaced-out heading label for the state of a fleet or timer: ACTIVE, COMPLETED, CANCELLED, EXPIRED. It is the word counterpart of `Countdown`, and shares its letter-spacing so the two swap in place.',
                    '`tone="danger"` is the cancelled/expired red; the default is `--highlight`. `blink` adds the shared `blink-animation` for something live. Extra attributes and `class` pass through to the `<p>`. Text is always uppercase, so write it in normal case.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        tone: radio_control(['highlight', 'danger'] as const, '`danger` is the cancelled / expired red.'),
        blink: { control: 'boolean', description: 'Pulse the text to show something live.' },
        class: { control: 'text', description: 'Extra classes.' },
    },
    args: {
        tone: 'highlight',
        blink: false,
        slots: { default: 'Active' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Play) => {
        const text = within(canvasElement).getByText('Active')
        await expect(text).toHaveClass('status-text')
        await expect(text).not.toHaveClass('status-text--danger')
        await expect(text).not.toHaveClass('blink-animation')
    },
}

export const Danger = {
    args: { tone: 'danger', slots: { default: 'Cancelled' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Cancelled')).toHaveClass('status-text--danger')
    },
}

export const Expired = {
    args: { tone: 'danger', slots: { default: 'Expired' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Expired')).toHaveClass('status-text--danger')
    },
}

export const Blinking = {
    args: { blink: true, slots: { default: 'Fleet live' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Fleet live')).toHaveClass('blink-animation')
    },
}

export const Completed = {
    args: { slots: { default: 'Completed' } },
    play: async ({ canvasElement }: Play) => {
        await expect(within(canvasElement).getByText('Completed').tagName).toBe('P')
    },
}

export const PassThroughAttributes = {
    args: { id: 'fleet-state', 'aria-live': 'polite', class: 'text-center', slots: { default: 'Active' } },
    play: async ({ canvasElement }: Play) => {
        const text = within(canvasElement).getByText('Active')
        await expect(text).toHaveAttribute('id', 'fleet-state')
        await expect(text).toHaveAttribute('aria-live', 'polite')
        await expect(text).toHaveClass('text-center')
    },
}
