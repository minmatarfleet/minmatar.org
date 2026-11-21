import { expect, within } from 'storybook/test'
import DamageBadge from '@components/blocks/DamageBadge.astro'
import type { PlayArgs } from './_helpers'
import { damage_two_way, damage_only_dealt, damage_only_taken, damage_none, damage_big } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/DamageBadge',
    component: DamageBadge,
    parameters: {
        docs: {
            description: {
                component: 'A badge for one ship\'s damage in a fight: the hull icon and name, a blue line for damage dealt to the enemy and a red line for damage taken, each with the total, damage per volley and volley count. A line only shows when that side fired. It appears in the battle report on a finished fleet page (`/fleets/history/<id>`). The scenarios show a two-way trade, one-sided fights, a hull that did nothing and a capital-scale total.',
            },
        },
    },
    argTypes: {
        damage: { control: 'object', description: 'The ship\'s damage (`Damage`): totals, per-volley damage and volley counts both ways.' },
    },
    args: { damage: damage_two_way },
}

export const DealtAndTaken = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Hurricane Fleet Issue')).toBeVisible()
        await expect(canvas.getByText('112,840 (1,820 per volley) - 62 volleys')).toBeVisible()
        await expect(canvas.getByText('48,210 (1,340 per volley) - 36 volleys')).toBeVisible()
    },
}

export const OnlyDealt = {
    args: { damage: damage_only_dealt },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/62 volleys/)).toBeVisible()
        await expect(canvas.queryByText(/36 volleys/)).toBeNull()
    },
}

export const OnlyTaken = {
    args: { damage: damage_only_taken },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/36 volleys/)).toBeVisible()
        await expect(canvas.queryByText(/62 volleys/)).toBeNull()
    },
}

export const NoDamage = {
    args: { damage: damage_none },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Scimitar')).toBeVisible()
        await expect(canvas.queryByText(/volleys/)).toBeNull()
    },
}

export const CapitalScale = {
    args: { damage: damage_big },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByText('18,204,113 (4,820 per volley) - 3,776 volleys')).toBeVisible()
    },
}
