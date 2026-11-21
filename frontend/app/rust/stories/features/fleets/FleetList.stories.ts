import { expect, within, waitFor } from 'storybook/test'
import FleetList from '@components/blocks/FleetList.astro'
import {
    typical_fleets, busy_fleets, history_fleets, active_fleet, upcoming_strategic, hurricane_doctrine,
    supply_contracts, fc_metrics, upcoming_non_strategic, tribe_fleet, open_tribe_fleet,
} from '../../../fixtures/features/fleets'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

// The hero carousel (LandingSwiper) starts the site's global `Swiper` after a short timer. Storybook's head does
// not load the library in every environment, so a no-op stand-in keeps the timer from throwing.
const w = globalThis as any
if (!w.Swiper) w.Swiper = class { constructor() {} }

export default {
    title: 'Features/Fleets/FleetList',
    component: FleetList,
    parameters: {
        docs: {
            description: {
                component: [
                    'The fleets hub list: `/fleets/upcoming` and `/fleets/history`. A grid of fleet cards (FleetListItem), optionally topped by a full-screen hero for fleets that are running or about to run, and a Fleet Commanders ranking reel at the bottom.',
                    'The scenarios are the empty list, a typical week, a busy weekend (24 fleets), the history list (completed and cancelled fleets, no volunteer buttons), a list with an active fleet promoted to the hero, and the hub mixing alliance and tribe group fleets.',
                ].join('\n\n'),
            },
        },
        htmx: {
            '/partials/fleet_cover': '<div id="viewport-cover-oob"></div>',
        },
    },
    argTypes: {
        fleets: { control: 'object', description: 'Every fleet to list (FleetItem). Fleets in `active_fleets` are lifted out of the grid.' },
        active_fleets: { control: 'object', description: 'Fleets shown in the hero carousel above the grid.' },
        active_doctrines: { control: 'object', description: 'The doctrine of each active fleet, by index.' },
        history: { control: 'boolean', description: 'History mode: links go to /fleets/history and the volunteer button is hidden.' },
        supply_contracts: { control: 'object', description: 'Per active fleet, the doctrine\'s supply contracts, shown under the hero.' },
        fc_metrics: { control: 'object', description: 'Fleet Commander ranking for the reel; null or empty hides it.' },
    },
    args: { fleets: typical_fleets, active_fleets: [], active_doctrines: [], history: false, supply_contracts: [], fc_metrics: null },
}

const cards = (canvasElement: HTMLElement) => canvasElement.querySelectorAll('.fleet-list-item')

export const Typical = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(cards(canvasElement)).toHaveLength(5)
        await expect(canvas.getAllByRole('link', { name: 'View details' })).toHaveLength(5)
        await expect(canvas.getAllByRole('link', { name: 'Volunteer' })).toHaveLength(5)
        await settle(() => expect(canvas.getByText("Kel'dar Atram")).toBeVisible())
        await settle(() => expect(canvas.getByText('Vaenne Hroth')).toBeVisible())
        await expect(canvas.queryByText(/There are no fleets on schedule/)).toBeNull()
    },
}

export const Empty = {
    args: { fleets: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await settle(() => expect(within(canvasElement).getByText('There are no fleets on schedule. Be the one adding the first one.')).toBeVisible())
        await expect(cards(canvasElement)).toHaveLength(0)
    },
}

export const SingleFleet = {
    args: { fleets: [upcoming_strategic] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(cards(canvasElement)).toHaveLength(1)
        await expect(within(canvasElement).getByRole('link', { name: 'View details' })).toHaveAttribute('href', '/fleets/upcoming/9401')
    },
}

export const BusyWeekend = {
    args: { fleets: busy_fleets },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(cards(canvasElement)).toHaveLength(24)
        await expect(within(canvasElement).getAllByRole('link', { name: 'View details' })[23]).toHaveAttribute('href', '/fleets/upcoming/9523')
    },
}

export const History = {
    args: { fleets: history_fleets, history: true },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(cards(canvasElement)).toHaveLength(3)
        await expect(canvas.queryByRole('link', { name: 'Volunteer' })).toBeNull()
        await expect(canvas.getAllByRole('link', { name: 'View details' })[0]).toHaveAttribute('href', '/fleets/history/9390')
        await expect(canvas.getAllByText('Completed')).toHaveLength(2)
        await settle(() => expect(canvas.getByText('Cancelled')).toBeVisible())
    },
}

export const MixedAllianceAndTribeFleets = {
    args: { fleets: [upcoming_strategic, tribe_fleet, open_tribe_fleet, upcoming_non_strategic] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(cards(canvasElement)).toHaveLength(4)
        // Only the two group fleets carry the host chip and visibility tag.
        await expect(canvasElement.querySelectorAll('.fleet-host-tags')).toHaveLength(2)
    },
}

export const ActiveFleetHero = {
    args: {
        fleets: [active_fleet, ...typical_fleets],
        active_fleets: [active_fleet],
        active_doctrines: [hurricane_doctrine],
        supply_contracts: [supply_contracts],
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // The active fleet leaves the grid and is shown once, in the hero.
        await expect(cards(canvasElement)).toHaveLength(5)
        await settle(() => expect(canvas.getByText('In development')).toBeVisible())
        await expect(canvas.getAllByRole('link', { name: 'View details' }).some((a) => a.getAttribute('href') === '/fleets/upcoming/9399')).toBe(true)
        await expect(canvas.getAllByRole('link', { name: 'Volunteer' }).some((a) => a.getAttribute('href') === '/fleets/upcoming/9399/volunteer')).toBe(true)
        await expect(canvasElement.querySelector('[hx-get*="/partials/fleet_cover"]')).not.toBeNull()
    },
}

export const WithFleetCommanderRanking = {
    args: { fc_metrics },
    tags: ['browser'],
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.compensate-bottom-bar')).not.toBeNull()
        await expect(cards(canvasElement)).toHaveLength(5)
    },
}
