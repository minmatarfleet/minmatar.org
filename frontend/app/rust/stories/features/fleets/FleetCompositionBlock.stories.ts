import { expect, within, userEvent, waitFor } from 'storybook/test'
import FleetCompositionBlock from '@components/blocks/FleetCompositionBlock.astro'
import { composition, busy_composition, radar } from '../../../fixtures/features/fleets'

// The page-level Alpine state the collapse-all control sets (declared by the site's footer scripts).
Object.assign(globalThis, { global_collapse: false })

export default {
    title: 'Features/Fleets/FleetCompositionBlock',
    component: FleetCompositionBlock,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Composition tab of a running fleet (`/fleets/upcoming/<id>` for the FC): who is flying what, grouped by hull with collapsible pilot lists, and where the pilots are, grouped by solar system with the jumps from the staging system. Reload re-reads `fleet_composition` with a d-scan animation; Collapse all folds every hull group.',
                    'The scenarios are a small fleet, a busy fleet with 29 pilots, a single pilot (singular labels), and a fleet that has no members yet. The reload test is a browser story because it swaps the block through htmx.',
                ].join('\n\n'),
            },
        },
        htmx: {
            '/partials/fleet_composition': '<div id="fleet-composition-component"><p>Composition reloaded</p></div>',
        },
    },
    argTypes: {
        fleet_id: { control: 'number', description: 'Fleet to reload the composition for.' },
        composition: { control: 'object', description: 'Pilots grouped by hull type.' },
        fleet_radar: { control: 'object', description: 'Pilots grouped by solar system, with jumps from staging.' },
    },
    args: { fleet_id: 9399, composition, fleet_radar: radar },
}

export const SmallFleet = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Fleet composition' })).toBeVisible()
        await expect(canvas.getByText('9 pilots')).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Hurricane' })).toBeVisible()
        await expect(canvas.getByText('6 pilots')).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'Muninn' })).toBeVisible()
        await expect(canvasElement.querySelectorAll('#fleet-composition-dscan [data-member]')).toHaveLength(9)
        await expect(canvas.getByRole('heading', { name: 'Members location' })).toBeVisible()
        await expect(canvas.getByText('2 systems')).toBeVisible()
        const reload = canvas.getByRole('button', { name: 'Reload' })
        await expect(reload.getAttribute('hx-get')).toContain('/partials/fleet_composition?id=9399')
    },
}

export const BusyFleet = {
    args: { composition: busy_composition },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('29 pilots')).toBeVisible()
        await expect(canvas.getByText('18 pilots')).toBeVisible()
        await expect(canvasElement.querySelectorAll('#fleet-composition-dscan [data-member]')).toHaveLength(29)
    },
}

export const SinglePilot = {
    args: { composition: [{ ...composition[2] }], fleet_radar: [{ ...radar[0], members: [composition[2].members[0]] }] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // The header total, the hull group and the system group each say "1 pilot".
        await expect(canvas.getAllByText('1 pilot')).toHaveLength(3)
        await expect(canvas.getByText('1 system')).toBeVisible()
    },
}

export const NoMembersYet = {
    args: { composition: [], fleet_radar: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByText('No members found')).toHaveLength(2)
        // No count line while the roster is empty.
        await expect(canvas.queryByText(/pilots$/)).toBeNull()
    },
}

export const CollapsingAHull = {
    // x-collapse measures real layout, which the test DOM does not have.
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const hurricane = canvas.getByRole('heading', { name: 'Hurricane' })
        const roster = within(canvasElement.querySelector('#fleet-composition-dscan') as HTMLElement)
        const pilots = roster.getByText("Kel'dar Atram", { selector: 'p' })
        await expect(pilots).toBeVisible()
        await userEvent.click(hurricane)
        await waitFor(() => expect(pilots).not.toBeVisible())
        await userEvent.click(hurricane)
        await waitFor(() => expect(pilots).toBeVisible())
    },
}

export const ReloadSwapsTheBlock = {
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'Reload' }))
        await waitFor(() => expect(canvas.getByText('Composition reloaded')).toBeVisible())
        await expect(canvasElement.querySelector('[data-composition-context]')).toBeNull()
    },
}
