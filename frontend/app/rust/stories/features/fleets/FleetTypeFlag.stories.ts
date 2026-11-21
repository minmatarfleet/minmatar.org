import { expect, within } from 'storybook/test'
import FleetTypeFlag from '@components/blocks/FleetTypeFlag.astro'
import { FLEET_TYPE_LABELS } from '../../../fixtures/features/fleets'

const types = ['strategic', 'non_strategic', 'training', 'npsi'] as const

export default {
    title: 'Features/Fleets/FleetTypeFlag',
    component: FleetTypeFlag,
    parameters: {
        docs: {
            description: {
                component: [
                    'The fleet-type corner flag: Stratop (strategic), Non-strategic, Training or NPSI icon with a tooltip naming the type. It sits in the top-left corner of FC portraits on fleet cards, the fleet page header and the SRP candidate list.',
                    'The stories show each type and a fleet with no type, which renders nothing rather than guessing a flag.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        type: { control: 'select', options: [undefined, ...types], description: 'Fleet type; unset renders nothing.' },
        size: { control: { type: 'number', min: 16, max: 96 }, description: 'Edge length in px; the icons are drawn at 57.' },
    },
    args: { type: 'strategic', size: 57 },
}

const flag = (canvasElement: HTMLElement) => within(canvasElement).getByRole('img')

export const Strategic = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(flag(canvasElement)).toHaveAttribute('aria-label', FLEET_TYPE_LABELS.strategic)
        await expect(flag(canvasElement)).toHaveAttribute('data-tippy-content', FLEET_TYPE_LABELS.strategic)
        await expect(flag(canvasElement).getAttribute('style')).toContain('--flag-size: 57px')
    },
}

export const NonStrategic = {
    args: { type: 'non_strategic' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(flag(canvasElement)).toHaveAttribute('aria-label', FLEET_TYPE_LABELS.non_strategic)
    },
}

export const Training = {
    args: { type: 'training' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(flag(canvasElement)).toHaveAttribute('aria-label', FLEET_TYPE_LABELS.training)
    },
}

export const Npsi = {
    args: { type: 'npsi' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(flag(canvasElement)).toHaveAttribute('aria-label', FLEET_TYPE_LABELS.npsi)
    },
}

export const Small = {
    args: { type: 'training', size: 24 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(flag(canvasElement).getAttribute('style')).toContain('--flag-size: 24px')
    },
}

export const NoType = {
    args: { type: undefined },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).queryByRole('img')).toBeNull()
    },
}
