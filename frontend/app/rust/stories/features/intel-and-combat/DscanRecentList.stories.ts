import { expect, within, userEvent, waitFor } from 'storybook/test'
import DscanRecentList from '@components/blocks/DscanRecentList.astro'
import { recent_items } from '../../../fixtures/features/intel-and-combat'

export default {
    title: 'Features/Intel and combat/DscanRecentList',
    component: DscanRecentList,
    parameters: {
        docs: {
            description: {
                component: [
                    'The "Last 2 hours" feed on `/dscan/`: every d-scan, Local scan and intel ping shared recently, with the system, a one-line headline, hull thumbnails, who shared it and its age.',
                    'Filter buttons (All, D-scan, Local, Pings) are local Alpine state over the rendered rows. Hostile Local scans are highlighted, and a ping with no saved report is a plain row instead of a link.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: { items: { control: 'object', description: 'Recent items from the API, newest first.' } },
    args: { items: recent_items },
}

type Ctx = { canvasElement: HTMLElement }

export const Typical = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Last 2 hours' })).toBeVisible()
        await expect(canvasElement.querySelectorAll('li')).toHaveLength(4)
        await expect(canvas.getByText('38 ships')).toBeVisible()
        await expect(canvas.getByText('17 hostile')).toHaveClass('is-hostile')
        await expect(canvas.getByText('/ 52')).toBeVisible()
        await expect(canvas.getByText('+1')).toBeVisible()
        await expect(canvas.getByText('Amamake').closest('a')).toHaveAttribute('href', '/dscan/a8f3k2/')
    },
}

export const PingWithoutReportIsNotALink = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const row = canvas.getByText('Old Man Star').parentElement as HTMLElement
        await expect(row.tagName).toBe('DIV')
        await expect(canvas.getByText('6 ships')).toBeVisible()
        await expect(row.querySelector('.is-ping')).not.toBeNull()
    },
}

export const FilterByKind = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.click(canvas.getByRole('button', { name: 'Local' }))
        await expect(canvas.getByRole('button', { name: 'Local' })).toHaveAttribute('aria-pressed', 'true')
        await expect(canvas.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
        // Alpine's x-show applies the filter after the click, so wait for the rows to settle.
        const visible = () => Array.from(canvasElement.querySelectorAll('li')).filter((li) => (li as HTMLElement).style.display !== 'none')
        await waitFor(() => expect(visible()).toHaveLength(2))
    },
}

export const Empty = {
    args: { items: [] },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Nothing shared in the last 2 hours.')).toBeVisible()
    },
}
