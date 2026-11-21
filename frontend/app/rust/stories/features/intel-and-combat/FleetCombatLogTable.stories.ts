import { expect, within } from 'storybook/test'
import FleetCombatLogTable from '@components/blocks/FleetCombatLogTable.astro'
import { fleet_logs_one, fleet_logs_typical, fleet_logs_busy, fleet_logs_edge } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/FleetCombatLogTable',
    component: FleetCombatLogTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The combat logs recorded against a fleet, on the fleet page (`/fleets/<id>/`) and the After-action report. Each card names the pilot who logged it, when it was uploaded, what they flew and where, and links to `/intel/combatlog/<id>`.',
                    'The "Paste combatlog" button is hidden for closed fleets (`disabled`). The scenarios cover no logs, one log, a typical list, a long list, a closed fleet and logs with missing or very long names.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        saved_logs: { control: 'object', description: 'Logs recorded for the fleet.' },
        fleet_id: { control: 'number', description: 'Fleet the pasted log is attached to.' },
        disabled: { control: 'boolean', description: 'Hide the paste button (fleet is closed).' },
    },
    args: { saved_logs: fleet_logs_typical, fleet_id: 92221, disabled: false },
}

type Ctx = { canvasElement: HTMLElement }

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Combat Logs' })).toBeVisible()
        await expect(canvas.getByText('4 logs recorded')).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Add Combat Log' })).toBeVisible()
        const links = canvasElement.querySelectorAll('a[href*="/intel/combatlog/"]')
        await expect(links).toHaveLength(4)
        await expect(links[0]).toHaveAttribute('href', '/intel/combatlog/1')
        await expect(canvas.getByText(/On Scimitar pilot @ Auga/)).toBeVisible()
    },
}

export const SingleLog = {
    args: { saved_logs: fleet_logs_one },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('1 log recorded')).toBeVisible()
    },
}

export const NoLogsYet = {
    args: { saved_logs: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('0 logs recorded')).toBeVisible()
        await expect(canvasElement.querySelectorAll('a[href*="/intel/combatlog/"]')).toHaveLength(0)
        await expect(canvas.getByRole('button', { name: 'Add Combat Log' })).toBeVisible()
    },
}

export const ClosedFleetNoPaste = {
    args: { disabled: true },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByRole('button', { name: 'Add Combat Log' })).toBeNull()
        await expect(within(canvasElement).getByText('4 logs recorded')).toBeVisible()
    },
}

export const BusyFleet = {
    args: { saved_logs: fleet_logs_busy },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('18 logs recorded')).toBeVisible()
        await expect(canvasElement.querySelectorAll('a[href*="/intel/combatlog/"]')).toHaveLength(18)
    },
}

export const MissingAndLongNames = {
    args: { saved_logs: fleet_logs_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('heading', { level: 4 })).toHaveLength(2)
        await expect(canvas.getByText(/A Logger With An Extremely Long Character Name Here/)).toBeVisible()
        // The "On <character> @ <system>" line only appears when the log names a character.
        await expect(canvas.getAllByText(/^On /)).toHaveLength(1)
    },
}
