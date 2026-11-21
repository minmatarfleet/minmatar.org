import { expect, within, userEvent, waitFor } from 'storybook/test'
import IntelPartnersTable from '@components/blocks/IntelPartnersTable.astro'
import { partners_few, partners_busy, partners_pilot, ensure_edge_fade } from '../../../fixtures/features/intel-and-combat'

ensure_edge_fade()

export default {
    title: 'Features/Intel and combat/IntelPartnersTable',
    component: IntelPartnersTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'Who a subject shares kills with, on the entity profile pages under `/intel/affiliations/<kind>/<id>/`: groups on a group\'s kills, outside pilots on a group\'s kills, or the investigated groups a pilot flies with.',
                    '`share` is the share of the subject\'s sampled kills, and a pilot\'s rows have none, so `show_share` drops the column. Rows past `shown` are rendered but hidden until "Show all". The scenarios cover a short list, a busy list with the toggle, and a pilot\'s share-less table.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        rows: { control: 'object', description: 'Partner rows from the API.' },
        show_share: { control: 'boolean', description: 'Show the Share column.' },
        shown: { control: 'number', description: 'Rows visible before "Show all".' },
    },
    args: { rows: partners_few, show_share: true, shown: 10 },
}

type Ctx = { canvasElement: HTMLElement }

export const FewPartners = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('row')).toHaveLength(4)
        await expect(canvas.getByRole('columnheader', { name: 'Share' })).toBeVisible()
        await expect(canvas.getByText('Snuffed Out').closest('a') as HTMLElement).toHaveAttribute('href', '/intel/affiliations/alliance/99010001/')
        await expect(canvas.getByText('20%')).toBeVisible()
        // 0.04% of kills is shown as a floor, not as 0%.
        await expect(canvas.getByText('<0.1%')).toBeVisible()
        await expect(canvas.queryByRole('button', { name: /Show all/ })).toBeNull()
    },
}

export const BusyWithShowAll = {
    args: { rows: partners_busy },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // Header plus the first ten rows; the other four are rendered but hidden.
        await expect(canvas.getAllByRole('row')).toHaveLength(11)
        const more = canvas.getByRole('button', { name: 'Show all 14' })
        await expect(more).toHaveAttribute('aria-expanded', 'false')
        await userEvent.click(more)
        // Alpine swaps the label and reveals the hidden rows after the click, so wait for both.
        await waitFor(() => expect(canvas.getByRole('button', { name: 'Show fewer' })).toHaveAttribute('aria-expanded', 'true'))
        await waitFor(() => expect(canvas.getAllByRole('row')).toHaveLength(15))
    },
}

export const PilotPartnersNoShare = {
    args: { rows: partners_pilot, show_share: false },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('columnheader', { name: 'Share' })).toBeNull()
        await expect(canvas.getByRole('columnheader', { name: 'Militia' })).toBeVisible()
        await expect(canvas.getAllByRole('row')).toHaveLength(4)
    },
}

export const BlocLikelyAndMissing = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Pandemic Horde' })).toHaveAttribute('href', '/intel/affiliations/blocs/7/')
        // A partner with no bloc leaves the cell empty.
        await expect(canvasElement.querySelectorAll('.intel-bloc-tag')).toHaveLength(2)
    },
}
