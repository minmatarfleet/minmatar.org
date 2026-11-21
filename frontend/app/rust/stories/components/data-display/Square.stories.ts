import { expect } from 'storybook/test'
import Square from '@components/blocks/Square.astro'
import { BUTTON_COLORS, select_control } from '../../_controls'

const COLORS = [...BUTTON_COLORS, 'fleet-yellow']

export default {
    title: 'Components/Data display/Square',
    component: Square,
    parameters: {
        docs: {
            description: {
                component: 'A small solid color swatch (a 5px-padded inline block) used as a legend key next to a label, such as the red/green markers beside fleet-result numbers. It has no content and no role, so put the meaning in the adjacent text. `transparent` has no background rule, so it renders as an empty box.',
            },
        },
    },
    argTypes: {
        color: select_control(COLORS, 'Fill token: the same names as Button colors plus `fleet-yellow`.'),
    },
    args: { color: 'green' },
}

const square = (canvasElement: HTMLElement) => canvasElement.querySelector('div') as HTMLElement

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(square(canvasElement)).toHaveClass('green')
    },
}

export const FleetRed = {
    name: 'Fleet red',
    args: { color: 'fleet-red' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(square(canvasElement)).toHaveClass('fleet-red')
    },
}

export const AllianceBlue = {
    name: 'Alliance blue',
    args: { color: 'alliance-blue' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(square(canvasElement)).toHaveClass('alliance-blue')
    },
}

export const MilitiaPurple = {
    name: 'Militia purple',
    args: { color: 'militia-purple' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(square(canvasElement)).toHaveClass('militia-purple')
    },
}

export const FleetYellow = {
    name: 'Fleet yellow',
    args: { color: 'fleet-yellow', 'aria-hidden': 'true' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(square(canvasElement)).toHaveClass('fleet-yellow')
        await expect(square(canvasElement)).toHaveAttribute('aria-hidden', 'true')
    },
}
