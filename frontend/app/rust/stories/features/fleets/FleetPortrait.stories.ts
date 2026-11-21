import { expect, within } from 'storybook/test'
import FleetPortrait from '@components/blocks/FleetPortrait.astro'
import { FCS } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetPortrait',
    component: FleetPortrait,
    parameters: {
        docs: {
            description: {
                component: [
                    'The FC portrait with the fleet-type flag in its top-left corner and, when the FC runs the fleet in game on another character, that alt as a small inset in the bottom-right. It heads the fleet page and the fleet cards.',
                    'The stories cover each fleet type, the alt inset (the main stays the person, the alt is only where the fleet runs), a small size and a fleet with no type.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        character_id: { control: 'number', description: 'The FC main, whose portrait is shown.' },
        character_name: { control: 'text', description: 'Alt text for the portrait.' },
        type: { control: 'select', options: [undefined, 'strategic', 'non_strategic', 'training', 'npsi'], description: 'Fleet type shown as the corner flag.' },
        alt_character_id: { control: 'number', description: 'The character running the fleet in game, shown as an inset.' },
        alt_character_name: { control: 'text', description: 'Tooltip and alt text of the inset.' },
        size: { control: { type: 'number', min: 32, max: 256 }, description: 'Edge length in px.' },
    },
    args: { character_id: FCS.keldar.id, character_name: FCS.keldar.name, type: 'strategic', size: 112 },
}

export const StrategicFc = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const portrait = canvas.getByAltText("Kel'dar Atram")
        await expect(portrait.getAttribute('src')).toContain(`/characters/${FCS.keldar.id}/portrait`)
        await expect(canvas.getByRole('img', { name: 'Strategic fleet' })).toBeVisible()
        await expect(canvasElement.querySelector('.fleet-portrait__alt')).toBeNull()
    },
}

export const TrainingFc = {
    args: { character_id: FCS.vaenne.id, character_name: FCS.vaenne.name, type: 'training' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('img', { name: 'Training fleet' })).toBeVisible()
    },
}

export const NpsiFc = {
    args: { character_id: FCS.brakka.id, character_name: FCS.brakka.name, type: 'npsi' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('img', { name: 'NPSI fleet' })).toBeVisible()
    },
}

export const RunningOnAnAlt = {
    args: { alt_character_id: 2112954599, alt_character_name: 'Kel Scout Alt' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const alt = within(canvasElement).getByAltText('Kel Scout Alt')
        await expect(alt).toHaveClass('fleet-portrait__alt')
        await expect(alt).toHaveAttribute('title', 'Kel Scout Alt')
        await expect(alt.getAttribute('src')).toContain('/characters/2112954599/portrait')
        // The main stays the headline portrait.
        await expect(within(canvasElement).getByAltText("Kel'dar Atram")).toBeVisible()
    },
}

export const SmallInRow = {
    args: { size: 48, type: 'non_strategic', alt_character_id: 2112954599, alt_character_name: 'Kel Scout Alt' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.fleet-portrait')?.getAttribute('style')).toContain('--portrait-size: 48px')
        // Flag and inset have a minimum edge so they stay readable on small portraits.
        await expect(canvasElement.querySelector('.fleet-type-flag')?.getAttribute('style')).toContain('--flag-size: 22px')
    },
}

export const WithoutType = {
    args: { type: undefined },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).queryByRole('img', { name: /fleet$/ })).toBeNull()
        await expect(within(canvasElement).getByAltText("Kel'dar Atram")).toBeVisible()
    },
}
