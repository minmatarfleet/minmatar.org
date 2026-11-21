import { expect, within } from 'storybook/test'
import OrdersTable from '@components/blocks/OrdersTable.astro'
import {
    location_amamake_busy,
    location_amamake_empty,
    location_amamake_single,
    location_auga,
    location_rens,
} from '../../../fixtures/features/industry'

type Ctx = { canvasElement: HTMLElement }

// The station reel is a Swiper, which the site loads from a script tag. Storybook's browser has it; the test environment does not.
const w = globalThis as any
if (!w.Swiper) w.Swiper = class { slideNext() {} }

// The page's Alpine scope: every row asks `show_item($el)` whether it matches the search box.
const PageScope = (story: () => unknown) =>
    `<div x-data="{ show_item() { return true } }">${story()}</div>`

export default {
    title: 'Features/Industry/OrdersTable',
    component: OrdersTable,
    decorators: [PageScope],
    parameters: {
        docs: {
            description: {
                component: [
                    'The order board at `/industry/orders/` (open) and `/industry/orders/history/` (finished): a reel of stations with their order counts, then the active station\'s orders as rows. Clicking a station reloads the page filtered to it.',
                    'Scenarios show a station with many orders, a single order, an empty station (the "capacitor is empty" text), the other stations in the reel, and the history variant whose reel links point at the history path. The page supplies the Alpine `show_item()` search filter, so the stories wrap the block in a stand-in scope.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        active_orders_locations: { control: 'object', description: 'The station being shown and its orders (`OrderLocation`).' },
        non_active_orders_locations: { control: 'object', description: 'Other stations, rendered as the rest of the reel.' },
        is_history: { control: 'boolean', description: 'History view: reel links go to `/industry/orders/history`.' },
    },
    args: {
        active_orders_locations: location_amamake_busy,
        non_active_orders_locations: [location_rens, location_auga],
        is_history: false,
    },
}

export const BusyStation = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[id^="order-item-"]')).toHaveLength(12)
        await expect(canvas.getByText('12 orders')).toBeInTheDocument()
        await expect(canvas.getByText('2 orders')).toBeInTheDocument()
        await expect(canvas.getByText('1 order')).toBeInTheDocument()
        await expect(canvasElement.querySelector('a[href="/industry/orders/8300/"]')).not.toBeNull()
    },
}

export const SingleOrder = {
    args: { active_orders_locations: location_amamake_single, non_active_orders_locations: [] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[id^="order-item-"]')).toHaveLength(1)
        await expect(canvas.getByText('1 order')).toBeInTheDocument()
        await expect(canvas.getByText('Hurricane')).toBeInTheDocument()
    },
}

export const EmptyStation = {
    args: { active_orders_locations: location_amamake_empty, non_active_orders_locations: [location_rens] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('[id^="order-item-"]')).toHaveLength(0)
        await expect(canvas.getByText('0 orders')).toBeInTheDocument()
        await expect(canvas.getByText('The capacitor is empty!')).toBeInTheDocument()
    },
}

export const StationLinks = {
    play: async ({ canvasElement }: Ctx) => {
        const hrefs = [...canvasElement.querySelectorAll('a')].map(a => a.getAttribute('href') ?? '')
        await expect(hrefs.some(href => href.startsWith('/industry/orders?location_name=Rens'))).toBe(true)
        await expect(hrefs.some(href => href.startsWith('/industry/orders?location_name=Auga'))).toBe(true)
        await expect(hrefs.some(href => href.includes('/history'))).toBe(false)
    },
}

export const History = {
    args: { is_history: true, active_orders_locations: location_rens, non_active_orders_locations: [location_amamake_single] },
    play: async ({ canvasElement }: Ctx) => {
        const hrefs = [...canvasElement.querySelectorAll('a')].map(a => a.getAttribute('href') ?? '')
        await expect(hrefs.some(href => href.startsWith('/industry/orders/history?location_name='))).toBe(true)
        await expect(canvasElement.querySelectorAll('[id^="order-item-"]')).toHaveLength(2)
    },
}
