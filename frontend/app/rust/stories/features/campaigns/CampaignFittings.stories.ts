import { expect, within } from 'storybook/test'
import CampaignFittings from '@components/blocks/CampaignFittings.astro'
import { fittings_edge, fittings_single, fittings_typical } from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Features/Campaigns/CampaignFittings',
    component: CampaignFittings,
    parameters: {
        docs: {
            description: {
                component: [
                    'The campaign\'s recommended fits, a row of links under the briefing on `/campaigns/<slug>/`. Each chip names the role (falling back to the ship, then the fit name), links to the fitting page and carries an SRP tag when losses in that fit are reimbursed.',
                    'Scenarios: a typical doctrine of five fits, a single fit, no fits (nothing renders), and edge cases (a very long role label, a fit without a role label, a row without a fitting id that must be hidden).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fittings: { control: 'object', description: 'Campaign fits in display order; rows with no `fitting_id` are skipped.' },
    },
    args: { fittings: fittings_typical },
}

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Campaign fits')).toBeVisible()
        await expect(canvas.getAllByRole('link')).toHaveLength(5)
        const dps = canvas.getByRole('link', { name: /DPS/ })
        await expect(dps.getAttribute('href')).toMatch(/^\/ships\/fittings\/normal\/9001/)
        await expect(canvas.getByRole('link', { name: /Logistics/ })).toBeVisible()
        // Sabre is not SRP eligible; the other four are.
        await expect(canvas.getAllByText('SRP')).toHaveLength(4)
        // No role label: falls back to the ship name.
        await expect(canvas.getByRole('link', { name: /Vagabond/ })).toBeVisible()
    },
}

export const SingleFit = {
    args: { fittings: fittings_single },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('link')).toHaveLength(1)
        await expect(canvas.getByRole('link', { name: /Logi Anchor/ })).toBeVisible()
    },
}

export const NoFits = {
    args: { fittings: [] },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByText('Campaign fits')).toBeNull()
        await expect(canvasElement.querySelector('.campaign-fittings')).toBeNull()
    },
}

export const EdgeCases = {
    args: { fittings: fittings_edge },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // The row without a fitting id is dropped.
        await expect(canvas.getAllByRole('link')).toHaveLength(2)
        await expect(canvas.queryByText(/Hidden because no fitting id/)).toBeNull()
        await expect(canvas.getByText(/Doctrine Battleship With A Remarkably Long Role Label/)).toBeVisible()
        await expect(canvas.getByRole('link', { name: /Muninn/ })).toBeVisible()
    },
}
