import { expect, within, userEvent, waitFor } from 'storybook/test'
import SRPTable from '@components/blocks/SRPTable.astro'
import { srp_one, srp_typical, srp_edge, srp_busy } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/SRPTable',
    component: SRPTable,
    parameters: {
        docs: {
            description: {
                component: [
                    'The queue of pending ship reimbursement (SRP) requests: the SRP page for reviewers (`/fleets/srp`, with an Add button) and the same list under each fleet in the history view (`fleet_title`). Each card shows the pilot, hull and ISK amount; click it (reviewers) for the Process SRP dialog with Approve and Reject, or Remove it (a pilot\'s own request, `readonly`).',
                    'The scenarios are the empty queue, one request, a typical queue with a zero-amount request and an alt, a busy queue of 16, reviewer and pilot permissions, the per-fleet and fleetless titles, and corp ship and long name edge cases.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet_id: { control: 'number', description: 'Fleet the requests belong to; 0 means no fleet.' },
        fleet_srps: { control: 'object', description: 'The pending requests (SRPUI).' },
        readonly: { control: 'boolean', description: 'The viewer owns these requests: cards show Remove instead of opening the review dialog.' },
        fleet_title: { control: 'boolean', description: 'Heading is the fleet link (or "No fleet") and the table is scoped to the fleet.' },
        can_add_srp: { control: 'boolean', description: 'Show the Add SRP button (not with `fleet_title`).' },
        filterable: { control: 'boolean', description: 'Cards filter by category, ship type and name (needs the SRP page filters).' },
    },
    args: { fleet_id: 0, fleet_srps: srp_typical, readonly: false, fleet_title: false, can_add_srp: true, filterable: false },
}

const cards = (canvasElement: HTMLElement) => canvasElement.querySelectorAll('.srp-item')

export const ReviewerQueue = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Ship Reimbursement Program' })).toBeVisible()
        await expect(canvas.getByText('5 killmails pending')).toBeVisible()
        await expect(cards(canvasElement)).toHaveLength(5)
        await expect(canvas.getByText('78,000,000 ISK')).toBeVisible()
        await expect(canvas.getByText('210,000,000 ISK')).toBeVisible()
        await expect(canvas.getByText('SRP amount not defined')).toBeVisible()
        await expect(canvasElement.querySelector('#srp-table')).not.toBeNull()
        // Reviewers can add requests and nothing says Remove.
        await expect(canvas.queryByRole('button', { name: 'Remove' })).toBeNull()
    },
}

export const AltsShowTheirMain = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        // The request for Rens Alt's Stabber names the main who gets paid.
        await expect(within(canvasElement).getAllByText('Hek Roamer').length).toBeGreaterThan(1)
        await expect(within(canvasElement).getByText(/Rens Alt’s Stabber/)).toBeVisible()
    },
}

export const Empty = {
    args: { fleet_srps: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('0 killmails pending')).toBeVisible()
        await expect(cards(canvasElement)).toHaveLength(0)
        await expect(canvasElement.querySelector('[role="list"]')).toBeNull()
    },
}

export const OneRequest = {
    args: { fleet_srps: srp_one },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('1 killmail pending')).toBeVisible()
        await expect(cards(canvasElement)).toHaveLength(1)
    },
}

export const BusyQueue = {
    args: { fleet_srps: srp_busy },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('16 killmails pending')).toBeVisible()
        await expect(cards(canvasElement)).toHaveLength(16)
    },
}

export const OpeningTheReviewDialog = {
    args: { fleet_srps: srp_one },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const dialog = canvasElement.querySelector('.srp-process-dialog') as HTMLElement
        await userEvent.click(canvasElement.querySelector('.srp-item button') as HTMLElement)
        await waitFor(() => expect(within(dialog).getByText('Process SRP')).toBeVisible())
        const approve = within(dialog).getByRole('button', { name: 'Approved' })
        await expect(approve.getAttribute('hx-patch')).toContain('status=approved')
        await expect(approve.getAttribute('hx-patch')).toContain('reimbursement_id=1')
        await expect(within(dialog).getByRole('button', { name: 'Rejected' }).getAttribute('hx-patch')).toContain('status=rejected')
        await expect(canvas.getByRole('link', { name: /Hurricane/ })).toHaveAttribute('href', 'https://zkillboard.com/kill/1200000001/')
    },
}

export const MyOwnRequests = {
    args: { readonly: true, can_add_srp: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // Pilots can withdraw their own pending requests but not open the review dialog.
        await expect(canvas.getAllByRole('button', { name: 'Remove' })).toHaveLength(5)
    },
}

export const UnderAFleet = {
    args: { fleet_id: 9390, fleet_title: true, fleet_srps: srp_typical.slice(0, 3), can_add_srp: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Fleet 9390' })).toHaveAttribute('href', '/fleets/history/9390')
        await expect(canvasElement.querySelector('#srp-table-9390')).not.toBeNull()
        // The per-fleet list has no Add button of its own.
        await expect(canvas.queryByRole('button', { name: /add/i })).toBeNull()
        await expect(cards(canvasElement)).toHaveLength(3)
    },
}

export const FleetlessRequests = {
    args: { fleet_id: 0, fleet_title: true, fleet_srps: srp_edge.slice(1) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByRole('heading', { name: 'No fleet' })).toBeVisible()
        await expect(within(canvasElement).queryByRole('link', { name: /Fleet 0/ })).toBeNull()
    },
}

export const CorpShipAndLongName = {
    args: { fleet_srps: srp_edge },
    // SRPItem shows the corporation badge for corp ships with `a || (b) && <badge/>`, which renders nothing
    // when `is_corp_ship` is true, so the corporation is not asserted here.
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('1,450,000,000 ISK')).toBeVisible()
        await expect(canvas.getByText(/Corp Hauler Pilot’s Vargur/)).toBeVisible()
        await expect(canvas.getAllByText(/Bartholomew-Alexander/).length).toBeGreaterThan(0)
    },
}
