import { expect, userEvent, within } from 'storybook/test'
import FittingSlot from '@components/blocks/FittingSlot.astro'
import type { PlayArgs } from './_helpers'
import { autocannon_t2, autocannon_faction, autocannon_officer, fitting_slot_empty } from '../../../fixtures/features/ships'

const TOOLTIP_PARTIAL = '/partials/module_tooltip_component'

export default {
    title: 'Features/Ships/FittingSlot',
    component: FittingSlot,
    parameters: {
        docs: {
            description: {
                component: [
                    'One slot in the fitting picture on `/ships/fittings/render/` and in the custom fitting builder: an octagon holding the module icon, ringed in the colour of its meta group (Tech II, faction, officer and so on). An empty slot shows the placeholder for its slot type.',
                    'Hovering a module loads its tooltip from `/partials/module_tooltip_component` through Tippy. In Rust that partial is mocked with a stand-in that echoes the module name; the tooltip story is tagged `browser` because the request needs htmx.',
                ].join('\n\n'),
            },
        },
        htmx: {
            [TOOLTIP_PARTIAL]: (url: URL) => `<p class="module-tooltip">${url.searchParams.get('module_name') ?? ''}</p>`,
        },
    },
    argTypes: {
        ship_slot: { control: 'object', description: 'The module in the slot (`Module`), or null for an empty slot.' },
        slot_type: { control: 'select', options: ['High Slots', 'Medium Slots', 'Low Slots', 'Rig Slots'], description: 'Which slot kind an empty slot shows.' },
        placement: { control: 'select', options: ['top', 'right', 'bottom', 'left'], description: 'Side the module tooltip opens on.' },
    },
    args: { ship_slot: autocannon_t2, slot_type: 'High Slots', placement: 'bottom' },
}

export const Tech2Module = {
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelector('.fitting-slot')).toHaveClass('tech-2')
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('2889')
    },
}

export const FactionModule = {
    args: { ship_slot: autocannon_faction },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelector('.fitting-slot')).toHaveClass('faction')
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('16050')
    },
}

export const OfficerModule = {
    args: { ship_slot: autocannon_officer, placement: 'right' },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelector('.fitting-slot')).toHaveClass('officer')
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('85010')
    },
}

export const EmptyLowSlot = {
    args: { ship_slot: fitting_slot_empty, slot_type: 'Low Slots' },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelector('.fitting-slot')).toHaveClass('empty')
        // No module picture: the slot shows the low-slot placeholder icon instead.
        await expect(canvasElement.querySelector('.fitting-slot picture')).toBeNull()
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('Icon_fit_low')
    },
}

export const TooltipLoadsModule = {
    tags: ['browser'],
    play: async ({ canvasElement }: PlayArgs) => {
        await userEvent.hover(canvasElement.querySelector('img') as HTMLImageElement)
        await within(document.body).findByText('200mm AutoCannon II', {}, { timeout: 4000 })
        const requests: { url: string }[] = (window as unknown as { __rust_htmx_requests?: { url: string }[] }).__rust_htmx_requests ?? []
        const last = new URL(requests[requests.length - 1].url, 'http://rust.local')
        await expect(last.pathname).toBe(TOOLTIP_PARTIAL)
        await expect(last.searchParams.get('module_name')).toBe('200mm AutoCannon II')
    },
}
