import { expect, within } from 'storybook/test'
import FleetMiningResults from '@components/blocks/FleetMiningResults.astro'
import { mining_fleet, mining_fleet_no_timeline } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetMiningResults',
    component: FleetMiningResults,
    parameters: {
        docs: {
            description: {
                component: [
                    "A mining fleet's results (`/partials/fleet_mining_component`): the live **Mining** tab, and the **After Action Report** once the fleet is over. The dispatch view shows ore, m³ per hour and the ISK estimate, the fleet's running total with roster-change markers (▲ joins, ▼ leaves, merged per 15-minute boundary), and one strip per pilot (green = ore, red = idle in the fleet, faint = waiting for a reading, outline = not in the fleet). Below it: ore by pilot and a newest-first log.",
                    'The scenarios are a finished 90-minute fleet (an idle pilot, a multiboxer whose two characters leave together, a pilot with no mining scope) and a fleet with no timeline yet.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        mining: { control: 'object', description: 'GET /api/fleets/{id}/mining (`FleetMining`).' },
    },
    args: { mining: mining_fleet },
}

type Ctx = { canvasElement: HTMLElement }

export const Finished = {
    name: 'Finished fleet',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Fleet ore over time')).toBeInTheDocument()
        await expect(canvasElement.querySelectorAll('.dispatch-cell.idle').length).toBeGreaterThanOrEqual(2)
        // The two boxer characters leaving at once are one marker.
        await expect(canvasElement.querySelectorAll('.marker-group')).toHaveLength(1)
        await expect(canvas.getAllByText('Boxer Alt One').length).toBeGreaterThan(0)
        await expect(canvas.getAllByText('No mining scope').length).toBeGreaterThan(0)
    },
}

export const NoTimeline = {
    name: 'No timeline yet',
    args: { mining: mining_fleet_no_timeline },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Ore mined')).toBeInTheDocument()
        await expect(canvasElement.querySelector('.fleet-mining-dispatch')).toBeNull()
    },
}
