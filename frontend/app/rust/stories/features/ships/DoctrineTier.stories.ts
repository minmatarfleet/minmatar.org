import { expect, within } from 'storybook/test'
import DoctrineTier from '@components/blocks/DoctrineTier.astro'
import type { PlayArgs } from './_helpers'
import { rifter_fitting, fittings_t1_busy, hurricane_fitting, stabber_fitting, long_name_fitting, vagabond_fitting, fittings_busy } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/DoctrineTier',
    component: DoctrineTier,
    parameters: {
        docs: {
            description: {
                component: 'A grid of fitting cards for one tier of a doctrine (primary, support, utility, alts, capitals), each linking to its fitting page. It is the building block of the doctrine page, `/ships/doctrines/<id>-<name>/`. The scenarios show a lone fitting, a small tier, a busy tier that wraps over several rows and a fit with no tags and a very long name.',
            },
        },
    },
    argTypes: {
        fittings: { control: 'object', description: 'The fittings in the tier. Each card is titled by ship name and subtitled by the fitting type.' },
    },
    args: { fittings: [rifter_fitting] },
}

const links = (canvasElement: HTMLElement) => within(canvasElement).getAllByRole('listitem')

export const SingleFitting = {
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(links(canvasElement)).toHaveLength(1)
        await expect(within(canvasElement).getByRole('heading', { level: 3 })).toHaveTextContent('Rifter')
        await expect(links(canvasElement)[0].getAttribute('href')).toBe('/ships/fittings/normal/1201-rifter-amamake-brawler/')
    },
}

export const SmallTier = {
    args: { fittings: [hurricane_fitting, stabber_fitting, rifter_fitting] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(links(canvasElement).map(a => a.getAttribute('href'))).toEqual([
            '/ships/fittings/normal/1203-hurricane-autocannon-fleet/',
            '/ships/fittings/normal/1202-stabber-kite/',
            '/ships/fittings/normal/1201-rifter-amamake-brawler/',
        ])
        await expect(within(canvasElement).getAllByRole('heading', { level: 3 }).map(h => h.textContent)).toEqual(['Hurricane', 'Stabber', 'Rifter'])
    },
}

export const BusyTier = {
    args: { fittings: fittings_t1_busy },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(links(canvasElement)).toHaveLength(16)
    },
}

export const MixedMetaGroups = {
    // Tech II, Tech III and Faction cards carry an inline <style>; happy-dom (the vitest DOM) drops the rest of the grid after the first.
    tags: ['browser'],
    args: { fittings: fittings_busy },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(links(canvasElement)).toHaveLength(10)
        await expect(canvasElement.querySelectorAll('.ship-type-icon svg').length).toBeGreaterThanOrEqual(5)
        await expect(links(canvasElement)).toContain(links(canvasElement).find(a => a.getAttribute('href')?.includes(`${vagabond_fitting.id}`)))
    },
}

export const LongNamesNoTags = {
    args: { fittings: [long_name_fitting, { ...rifter_fitting, id: 1291, tags: [] }] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(links(canvasElement)).toHaveLength(2)
        // The card hides the fitting name in a filter list the search reads.
        await expect(canvasElement.textContent).toContain(long_name_fitting.fitting_name)
    },
}

export const Empty = {
    args: { fittings: [] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelectorAll('[role="listitem"]')).toHaveLength(0)
        await expect(canvasElement.querySelector('[role="list"]')).not.toBeNull()
    },
}
