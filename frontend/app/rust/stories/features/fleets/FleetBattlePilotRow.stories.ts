import { expect, within } from 'storybook/test'
import FleetBattlePilotRow from '@components/blocks/FleetBattlePilotRow.astro'
import {
    battle_pilot_survivor, battle_pilot_lost, battle_pilot_multi_hull, battle_pilot_no_icon, battle_pilot_long_name,
} from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetBattlePilotRow',
    component: FleetBattlePilotRow,
    parameters: {
        docs: {
            description: {
                component: 'One pilot on a side of a fleet battle report (`/fleets/<id>/report`): the hull they lost linking to its killmail, the name linking to zKillboard, damage with its share of the team, kills, ISK lost and the corporation and alliance logos. Other hulls they flew sit as small icons after the ship name, and a pod loss gets its own link. The scenarios show a survivor, a lost hull, a pilot who lost two hulls and a pod, a pilot with no hull icon and a long name.',
            },
        },
    },
    argTypes: {
        row: { control: 'object', description: 'The pilot row the report built: names, hull, killmail links, damage, kills, loss and logos.' },
    },
    args: { row: battle_pilot_lost },
    decorators: [(Story: () => string) => `<div style="width: 760px; max-width: 100%">${Story()}</div>`],
}

export const Survivor = {
    args: { row: battle_pilot_survivor },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Vaenne Hroth' })).toHaveAttribute('href', 'https://zkillboard.com/character/2112954533/')
        await expect(canvasElement.querySelector('.br-pilot')).not.toHaveClass('br-pilot--lost')
        await expect(canvas.getByText('Scimitar')).toBeVisible()
        await expect(canvas.getAllByText('640,000').length).toBeGreaterThan(0)
        await expect(canvasElement.querySelector('a[href*="/kill/"]')).toBeNull()
    },
}

export const LostHull = {
    args: { row: battle_pilot_lost },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('.br-pilot')).toHaveClass('br-pilot--lost')
        await expect(canvasElement.querySelector('a[href="https://zkillboard.com/kill/134510244/"]')).not.toBeNull()
        await expect(canvas.getAllByText('18,400,000 ISK').length).toBeGreaterThan(0)
        await expect(canvasElement.querySelector('.br-pilot__top')).not.toBeNull()
    },
}

export const MultiHullWithPod = {
    args: { row: battle_pilot_multi_hull },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('2 hulls').length).toBeGreaterThan(0)
        await expect(canvasElement.querySelector('a[href="https://zkillboard.com/kill/134510260/"]')).not.toBeNull()
        await expect(canvasElement.querySelector('a[href="https://zkillboard.com/kill/134510250/"]')).not.toBeNull()
        await expect(canvasElement.querySelector('img[alt="Scimitar, survived"]')).not.toBeNull()
        await expect(canvas.getByRole('link', { name: 'Tarsus Rennir' })).toBeVisible()
    },
}

export const NoHullIcon = {
    args: { row: battle_pilot_no_icon },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // No hull: the pilot's portrait stands in for the ship icon.
        const icon = canvasElement.querySelector('img.br-pilot__icon')
        await expect(icon?.getAttribute('src')).toContain(`/characters/${battle_pilot_no_icon.character_id}/portrait`)
        await expect(within(canvasElement).getByRole('link', { name: 'Ilsa Verhaaren' })).toBeVisible()
    },
}

export const NoCharacter = {
    args: { row: { ...battle_pilot_no_icon, character_id: 0, name: 'Undisclosed' } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // No hull and no character: EVE's default silhouette.
        const icon = canvasElement.querySelector('img.br-pilot__icon')
        await expect(icon?.getAttribute('src')).toContain('/characters/1/portrait')
    },
}

export const LongName = {
    args: { row: battle_pilot_long_name },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.br-pilot__name')?.textContent).toBe('Bartholomew-Alexander of the Heimatar Highlands the Third')
    },
}
