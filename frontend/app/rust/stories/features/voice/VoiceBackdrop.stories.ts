import { expect } from 'storybook/test'
import VoiceBackdrop from '@components/blocks/VoiceBackdrop.astro'

export default {
    title: 'Features/Voice/VoiceBackdrop',
    component: VoiceBackdrop,
    parameters: {
        docs: {
            description: {
                component: [
                    'The `/voice` backdrop, fixed behind the page and over its cover image: a dark wash that keeps the headline readable, a faint gold grid and a comms waveform along the bottom of the screen, every ninth bar in fleet red. It is decoration only (`aria-hidden`), and the bars stop moving when the pilot asks for reduced motion.',
                    'The scenarios show the default 72-bar wave and a sparse one.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        bars: { control: 'number', description: 'How many bars the waveform has.' },
    },
    args: { bars: 72 },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const backdrop = canvasElement.querySelector('.voice-backdrop') as HTMLElement
        await expect(backdrop).toHaveAttribute('aria-hidden', 'true')
        await expect(backdrop.querySelectorAll('.voice-backdrop__bar')).toHaveLength(72)
        await expect(backdrop.querySelectorAll('.voice-backdrop__bar.accent')).toHaveLength(8)
    },
}

export const Sparse = {
    args: { bars: 24 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('.voice-backdrop__bar')).toHaveLength(24)
    },
}
