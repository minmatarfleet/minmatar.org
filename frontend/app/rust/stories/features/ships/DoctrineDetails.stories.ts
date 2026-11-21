import { expect, within } from 'storybook/test'
import DoctrineDetails from '@components/blocks/DoctrineDetails.astro'
import type { PlayArgs } from './_helpers'
import { doctrine_full, doctrine_rifter_nonstrategic } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/DoctrineDetails',
    component: DoctrineDetails,
    // The "fleets in the past 30 days" caption reads `recently_fleets_count` from the page's Alpine scope.
    decorators: [(Story: () => unknown) => `<div x-data="{ recently_fleets_count: 0 }">${Story()}</div>`],
    parameters: {
        docs: {
            description: {
                component: 'The body of a doctrine page, `/ships/doctrines/<id>-<name>/`: the description, then a tier of fitting cards per role (primary, support, utility, alts, capitals, secondary) and the fleets that recently flew it. Tiers with no fittings are not drawn, and headings turn singular for a single fitting. The scenarios show a doctrine with every tier, a minimal one and a doctrine with no recent fleets.',
            },
        },
    },
    argTypes: {
        doctrine: { control: 'object', description: 'The doctrine (`DoctrineType`) with its fittings grouped by tier.' },
        recently_fleets: { control: 'object', description: 'Fleets that flew the doctrine in the last 30 days (`FleetItem[]`). An empty list shows the "no recent fleets" line; the list itself is the fleet block\'s own story.' },
    },
    args: { doctrine: doctrine_full, recently_fleets: [] },
}

export const EveryTier = {
    // Tech II, Tech III and Faction cards carry an inline <style>; happy-dom (the vitest DOM) drops the rest of the page after the first.
    tags: ['browser'],
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        const headings = canvas.getAllByRole('heading', { level: 2 }).map(h => h.textContent)
        // The secondary tier is labelled "Academy" (src/i18n/ui.ts: secondary_fitting).
        await expect(headings).toEqual([
            'Primary fittings', 'Support fittings', 'Utility fitting', 'Alts fitting', 'Capital fitting', 'Academy fitting', 'Used recently on',
        ])
        await expect(canvas.getByText(/Our standing strategic doctrine/)).toBeVisible()
        await expect(canvasElement.querySelectorAll('a[href^="/ships/fittings/normal/"]')).toHaveLength(8)
    },
}

export const MinimalPrimaryOnly = {
    args: { doctrine: doctrine_rifter_nonstrategic },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 2, name: 'Primary fitting' })).toBeVisible()
        await expect(canvas.queryByRole('heading', { level: 2, name: /Support/ })).toBeNull()
        await expect(canvas.getByRole('heading', { level: 2, name: 'Alts fitting' })).toBeVisible()
    },
}

export const NoRecentFleets = {
    args: { doctrine: doctrine_rifter_nonstrategic },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('No recent fleets using this doctrine.')).toBeVisible()
        await expect(canvas.getByText('0 fleets in the past 30 days')).toBeVisible()
    },
}
