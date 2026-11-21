import { expect, within } from 'storybook/test'
import RepairBadge from '@components/blocks/RepairBadge.astro'
import { repair_armor, repair_shield, repair_remote, repair_wasted } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/RepairBadge',
    component: RepairBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'One repair source in a combat log analysis (`/intel/combatlog/<id>`): the module (or rep type icon), how much it repaired, average and maximum per cycle, cycles run, and a bar for effective repairs, the share not wasted on overheal.',
                    'The scenarios cover an armor repairer, a shield booster with heavy overheal, a fully effective remote repairer, a module that wasted everything, and the rep-type icon variant.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        repair: { control: 'object', description: 'Totals for one repair module.' },
        rep_icon: { control: 'boolean', description: 'Show the shield/armor/hull icon instead of the module icon.' },
    },
    args: { repair: repair_armor, rep_icon: false },
}

type Ctx = { canvasElement: HTMLElement }

export const ArmorRepairer = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Large Armor Repairer II')).toBeVisible()
        await expect(canvas.getByText('1,268,400 (5,927 per cycle out of 6,320) - 214 cycles')).toBeVisible()
        await expect(canvas.getByText('94.20%')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '94.2')
        await expect(canvasElement.querySelector('img')).toHaveAttribute('src', expect.stringContaining('/types/3538/'))
    },
}

export const ShieldBoosterOverheal = {
    args: { repair: repair_shield },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Medium Shield Booster II')).toBeVisible()
        await expect(canvas.getByText('61.50%')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '61.5')
    },
}

export const FullyEffectiveRemote = {
    args: { repair: repair_remote },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('100.00%')).toBeVisible()
        await expect(within(canvasElement).getByText(/2,480,000/)).toBeVisible()
    },
}

export const AllWasted = {
    args: { repair: repair_wasted },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('0.00%')).toBeVisible()
        await expect(canvasElement.querySelector('progress')).toHaveAttribute('value', '0')
    },
}

export const RepTypeIcon = {
    args: { repair: repair_armor, rep_icon: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('img')).toHaveAttribute('src', '/images/icons/1_64_9.png')
    },
}
