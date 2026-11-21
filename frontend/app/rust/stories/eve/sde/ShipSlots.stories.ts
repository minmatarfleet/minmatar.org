import { expect, within } from 'storybook/test'
import ShipSlots from '@components/blocks/sde/ShipSlots.astro'
import { space_control } from '../../_controls'
import { ship } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const slot = (canvasElement: HTMLElement, key: string) =>
    canvasElement.querySelector(`[data-slot="${key}"]`) as HTMLElement

export default {
    title: 'EVE/SDE/ShipSlots',
    component: ShipSlots,
    parameters: {
        docs: {
            description: {
                component: [
                    'A hull\'s slot layout: high, mid, low and rig counts with the EVE slot icons, plus subsystems for strategic cruisers. `hardpoints` adds turret and launcher counts. The counts come in as the `counts` prop (`type.slots` from `search_types()`, or `get_ship_slots()` in `helpers/sde/search.ts`); the component never queries the SDE.',
                    'It is a list: each count reads as "3 high slots" to screen readers and the icons are decorative. The stories use the real hulls in `rust/fixtures/sde.json`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        counts: { control: 'object', description: '`{ high, mid, low, rig, subsystem, turrets?, launchers? }`.' },
        hardpoints: { control: 'boolean', description: 'Also show turret and launcher hardpoints.' },
        icon_size: space_control('Slot icon width.'),
        gap: { control: 'text', description: 'Gap between the counts (row and column).' },
    },
    args: {
        counts: ship('Rifter').slots,
        hardpoints: false,
        icon_size: 'var(--space-m)',
        gap: 'var(--space-2xs) var(--space-xs)',
    },
}

export const Default = {
    name: 'Rifter',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const list = canvas.getByRole('list', { name: 'Slot layout' })
        await expect(within(list).getAllByRole('listitem')).toHaveLength(4)
        await expect(slot(canvasElement, 'high')).toHaveTextContent(/3\s*high slots/)
        await expect(slot(canvasElement, 'mid')).toHaveAttribute('data-count', '3')
        await expect(slot(canvasElement, 'low')).toHaveAttribute('data-count', '4')
        await expect(slot(canvasElement, 'rig')).toHaveAttribute('data-count', '3')
        await expect(slot(canvasElement, 'subsystem')).toBeNull()
        await expect(slot(canvasElement, 'high').querySelector('[aria-hidden="true"] img')).not.toBeNull()
    },
}

export const WithHardpoints = {
    name: 'Hurricane with hardpoints',
    args: { counts: ship('Hurricane').slots, hardpoints: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(slot(canvasElement, 'high')).toHaveAttribute('data-count', '7')
        await expect(canvas.getByText('6 turrets')).toBeVisible()
        await expect(canvas.getByText('3 launchers')).toBeVisible()
    },
}

export const Battleship = {
    name: 'Typhoon',
    args: { counts: ship('Typhoon').slots },
    play: async ({ canvasElement }: Ctx) => {
        await expect(slot(canvasElement, 'high')).toHaveAttribute('data-count', '7')
        await expect(slot(canvasElement, 'mid')).toHaveAttribute('data-count', '5')
        await expect(slot(canvasElement, 'low')).toHaveAttribute('data-count', '7')
    },
}

export const TechIIRigs = {
    name: 'Vagabond (two rig slots)',
    args: { counts: ship('Vagabond').slots, hardpoints: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(slot(canvasElement, 'rig')).toHaveAttribute('data-count', '2')
        await expect(within(canvasElement).getByText('5 turrets')).toBeVisible()
    },
}

export const Subsystems = {
    name: 'Strategic cruiser (subsystems)',
    // A Loki hull: its high/mid/low slots come from the fitted subsystems.
    args: { counts: { high: 0, mid: 0, low: 0, rig: 3, subsystem: 4 } },
    play: async ({ canvasElement }: Ctx) => {
        const subsystem = slot(canvasElement, 'subsystem')
        await expect(subsystem).toHaveAttribute('data-count', '4')
        await expect(subsystem).toHaveTextContent(/4\s*subsystems/)
        await expect(within(canvasElement).getAllByRole('listitem')).toHaveLength(5)
    },
}

export const HardpointsWithoutData = {
    name: 'Hardpoints asked, none in the data',
    args: { counts: { high: 3, mid: 3, low: 4, rig: 3, subsystem: 0 }, hardpoints: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(slot(canvasElement, 'hardpoints')).toBeNull()
    },
}

export const SmallIcons = {
    args: { icon_size: 'var(--space-s)', gap: 'var(--space-3xs) var(--space-2xs)' },
    play: async ({ canvasElement }: Ctx) => {
        const root = canvasElement.querySelector('.ship-slots') as HTMLElement
        await expect(root.getAttribute('style')).toContain('--ship_slots_icon: var(--space-s)')
        await expect(within(canvasElement).getByRole('list').getAttribute('style')).toContain('--flex_inline_gap: var(--space-3xs) var(--space-2xs)')
    },
}
