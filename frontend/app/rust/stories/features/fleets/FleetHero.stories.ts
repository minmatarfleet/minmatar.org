import { expect, within, waitFor } from 'storybook/test'
import FleetHero from '@components/blocks/FleetHero.astro'
import {
    upcoming_strategic, upcoming_training, fleet_on_alt, fleet_with_long_text, bare_fleet, active_fleet,
    hurricane_doctrine, academy_doctrine, muninn_doctrine, supply_contracts, FCS,
} from '../../../fixtures/features/fleets'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

export default {
    title: 'Features/Fleets/FleetHero',
    component: FleetHero,
    parameters: {
        docs: {
            description: {
                component: [
                    'The big FC introduction at the top of the fleets hub (`/fleets/upcoming`, for the next or running fleet): the FC portrait, name and corporation, fleets led, staging system and station, doctrine, campaign, the objective and the briefing, and a scrolling strip of the doctrine\'s fittings. The default slot adds fact rows such as the countdown.',
                    'With `supply_contracts` the strip shows how many of each fit are on contract (red when none), plus a copy button; otherwise it labels the primary fittings. The scenarios cover a strategic fleet with a campaign, supply counts, a training doctrine, an FC running on an alt, long text, and a fleet with only the required fields.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        fleet: { control: 'object', description: 'The fleet (FleetItem).' },
        doctrine: { control: 'object', description: 'The fleet\'s doctrine, or null when it failed to load.' },
        supply_contracts: { control: 'object', description: 'Contract counts per fitting for the strip.' },
        show_fittings: { control: 'boolean', description: 'Render the scrolling fittings strip under the hero.' },
    },
    args: {
        fleet: upcoming_strategic,
        doctrine: hurricane_doctrine,
        supply_contracts: [],
        show_fittings: true,
        slots: { default: '<span class="rust-demo-box">Starts in 25:59:12</span>' },
    },
}

export const StrategicWithCampaign = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { level: 2, name: FCS.keldar.name })).toBeVisible())
        await settle(() => expect(canvas.getByRole('heading', { level: 4, name: /take back the Amamake gate camp/ })).toBeVisible())
        await settle(() => expect(canvas.getByText('Amamake', { selector: 'b' })).toBeVisible())
        await settle(() => expect(canvas.getByText('Freeport')).toBeVisible())
        await expect(canvas.getByRole('link', { name: /Hurricane Brawl/ }).getAttribute('href')).toContain('/ships/doctrines/12')
        await expect(canvas.getByRole('link', { name: 'Amamake Offensive' })).toHaveAttribute('href', '/campaigns/amamake-2026-11/')
        await settle(() => expect(canvas.getByText('41')).toBeVisible())
        await settle(() => expect(canvas.getByText('Starts in 25:59:12')).toBeVisible())
        await settle(() => expect(canvas.getByText(/Form up on the Rens undock/)).toBeVisible())
    },
}

export const FittingsStripWithoutContracts = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const links = [...canvasElement.querySelectorAll('a[href*="/ships/fittings/normal/"]')]
        await expect(links.length).toBeGreaterThanOrEqual(2)
        await expect(canvasElement.textContent).toContain('Hurricane - Rens Brawl')
        await expect(canvasElement.textContent).toContain('Scimitar - Logi')
        await expect(canvasElement.textContent).toContain('Primary fitting')
        await expect(canvasElement.querySelector('#supply-contracts')).toBeNull()
    },
}

export const WithSupplyContracts = {
    args: { supply_contracts },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const text = canvasElement.textContent ?? ''
        await expect(text).toContain('24 on contracts')
        await expect(text).toContain('0 on contracts')
        await expect(text).not.toContain('Primary fitting')
        // The copy button carries the whole stock line list for the FC to paste.
        await expect(canvasElement.querySelector('#supply-contracts, [id*="supply-contracts"]')).not.toBeNull()
    },
}

export const TrainingDoctrine = {
    args: { fleet: upcoming_training, doctrine: academy_doctrine },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { level: 2, name: FCS.vaenne.name })).toBeVisible())
        await settle(() => expect(canvas.getByText('Rens', { selector: 'b' })).toBeVisible())
        await settle(() => expect(canvas.getByText('Brutor Tribe Treasury')).toBeVisible())
        await settle(() => expect(canvas.getByText(/First-week pilots welcome/)).toBeVisible())
    },
}

export const FcRunningOnAnAlt = {
    args: { fleet: fleet_on_alt, doctrine: muninn_doctrine },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByText('Kel Scout Alt')).toBeVisible())
        await settle(() => expect(canvas.getByText('In game')).toBeVisible())
        await expect(canvas.getByRole('heading', { level: 2 })).toHaveTextContent(FCS.keldar.name)
    },
}

export const LongTextAndNames = {
    args: { fleet: fleet_with_long_text, doctrine: hurricane_doctrine },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { level: 2, name: FCS.long_one.name })).toBeVisible())
        await settle(() => expect(canvas.getByText('Old Man Star', { selector: 'b' })).toBeVisible())
        await expect(canvas.getByText('Voice is mandatory')).toBeInTheDocument()
    },
}

export const NoDoctrine = {
    args: { fleet: active_fleet, doctrine: null },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        // "Not set": without a doctrine there is no doctrine fact and no fittings strip.
        await expect(canvas.queryByText('Doctrine')).toBeNull()
        await expect(canvasElement.querySelector('a[href*="/ships/fittings/"]')).toBeNull()
        await settle(() => expect(canvas.getByRole('heading', { level: 2, name: FCS.keldar.name })).toBeVisible())
    },
}

export const OnlyRequiredFields = {
    // FleetHero always draws the corporation badge, which fetches the corporation by id: a fleet without
    // `corporation_id` makes it request `/corporations/undefined`, so the corporation is kept here.
    args: { fleet: { ...bare_fleet, corporation_id: FCS.vaenne.corporation_id, corporation_name: FCS.vaenne.corporation_name }, doctrine: null, slots: {} },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { level: 2, name: FCS.vaenne.name })).toBeVisible())
        await expect(canvas.queryByRole('heading', { level: 4 })).toBeNull()
        await expect(canvas.queryByText('Campaign')).toBeNull()
    },
}
