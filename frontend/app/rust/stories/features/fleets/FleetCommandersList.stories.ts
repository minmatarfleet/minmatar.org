import { expect, within } from 'storybook/test'
import FleetCommandersList from '@components/blocks/FleetCommandersList.astro'
import { commanders, FCS } from '../../../fixtures/features/fleets'

export default {
    title: 'Features/Fleets/FleetCommandersList',
    component: FleetCommandersList,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Commanders tab (`/fleets/commanders`): the Fleet Commanders tribe group in tiers, one per rank (Strategic FC, Skirmish FC, ...), highest first. Pilots without a rank form the plain "FC" tier at the bottom. Inside a tier the FC who has led the most fleets comes first, and pilots who have never led are dimmed.',
                    'The scenarios show the full roster, a single commander, an all-unranked roster, a busy roster of 24 and the empty state.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        commanders: { control: 'object', description: 'FleetCommander rows from the API: rank, fleets led, last led, timezone.' },
    },
    args: { commanders },
}

export const Typical = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        const tiers = canvas.getAllByRole('heading', { level: 2 }).map((h) => h.firstChild?.textContent?.trim())
        // Highest rank first, unranked "FC" last.
        await expect(tiers).toEqual(['Strategic FC', 'Skirmish FC', 'FC'])
        await expect(canvasElement.querySelectorAll('article')).toHaveLength(6)
        // Most fleets led comes first inside a tier.
        const strategic = [...canvasElement.querySelectorAll('section')[0].querySelectorAll('strong')].map((s) => s.textContent)
        await expect(strategic).toEqual([FCS.keldar.name, FCS.brakka.name])
        await expect(canvas.getByText(/112 fleets/)).toBeVisible()
        await expect(canvas.getByText(/1 fleet(?!s)/)).toBeVisible()
        await expect(canvas.getByText(/last Today/)).toBeVisible()
    },
}

export const IdleCommandersAreDimmed = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const idle = [...canvasElement.querySelectorAll('article.is-idle')]
        await expect(idle).toHaveLength(1)
        await expect(idle[0].textContent).toContain(FCS.ilsa.name)
        await expect(idle[0].textContent).toContain('0 fleets')
        await expect(idle[0].textContent).not.toContain('last ')
    },
}

export const SingleCommander = {
    args: { commanders: [commanders[0]] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('article')).toHaveLength(1)
        await expect(canvas.getByRole('heading', { level: 2 })).toHaveTextContent('Strategic FC1')
        await expect(canvas.getByText(FCS.keldar.name)).toBeVisible()
        await expect(canvas.getByText(FCS.keldar.corporation_name)).toBeVisible()
    },
}

export const AllUnranked = {
    args: { commanders: commanders.map((commander) => ({ ...commander, rank_name: null, rank_order: null })) },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const headings = within(canvasElement).getAllByRole('heading', { level: 2 })
        await expect(headings).toHaveLength(1)
        await expect(headings[0]).toHaveTextContent('FC6')
    },
}

export const BusyRoster = {
    args: {
        commanders: Array.from({ length: 24 }, (_, index) => ({
            ...commanders[index % commanders.length],
            user_id: 100 + index,
            primary_character_id: 2112980000 + index,
            primary_character_name: `Commander ${index + 1}`,
            fleets_total: 60 - index,
        })),
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelectorAll('article')).toHaveLength(24)
        await expect(canvasElement.querySelectorAll('section').length).toBeGreaterThanOrEqual(3)
    },
}

export const LongName = {
    args: { commanders: [commanders[5]] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(FCS.long_one.name)).toBeVisible()
    },
}

export const MissingPortraitAndCorp = {
    args: {
        commanders: [{ ...commanders[4], primary_character_id: null, primary_character_name: null, corporation_name: null }],
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('.fleet-commanders__no-portrait')).not.toBeNull()
        await expect(canvasElement.querySelector('img')).toBeNull()
        await expect(within(canvasElement).getByText('—')).toBeVisible()
    },
}

export const Empty = {
    args: { commanders: [] },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText('No fleet commanders yet.')).toBeVisible()
        await expect(canvasElement.querySelector('article')).toBeNull()
    },
}
