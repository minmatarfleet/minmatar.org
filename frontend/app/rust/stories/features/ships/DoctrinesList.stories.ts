import { expect, within } from 'storybook/test'
import DoctrinesList from '@components/blocks/DoctrinesList.astro'
import type { PlayArgs } from './_helpers'
import {
    doctrine_location_amamake, doctrine_location_rens, doctrine_location_auga, doctrine_location_all,
    doctrine_location_empty,
} from '../../../fixtures/features/ships'

// Swiper comes from the site's head scripts (Storybook's preview-head loads it); vitest's DOM has none.
if (typeof (globalThis as any).Swiper === 'undefined')
    (globalThis as any).Swiper = class { update() {} destroy() {} on() {} }

export default {
    title: 'Features/Ships/DoctrinesList',
    component: DoctrinesList,
    parameters: {
        docs: {
            description: {
                component: 'The doctrines index: a reel of market locations (Amamake, Rens, Auga...) with the active one highlighted, over a grid of doctrine cards linking to each doctrine page. It is the body of `/ships/doctrines/`, where `?location_id=` picks the location. The scenarios show the multi-location reel, a single location with no reel, the all-locations view and a location with no doctrines.',
            },
        },
    },
    argTypes: {
        active_doctrine_location_ui: { control: 'object', description: 'The location being shown (`DoctrineLocationUI`); id 0 means all locations.' },
        non_active_doctrine_location_ui: { control: 'object', description: 'The other locations, shown as reel slides. With none, the reel is hidden.' },
    },
    args: {
        active_doctrine_location_ui: doctrine_location_amamake,
        non_active_doctrine_location_ui: [doctrine_location_rens, doctrine_location_auga],
    },
}

const cards = (canvasElement: HTMLElement) => within(canvasElement).getAllByRole('list')[0].querySelectorAll('a.doctrine-card-container')

export const AmamakeWithReel = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelectorAll('a.doctrine-card-container')).toHaveLength(4)
        await expect(canvas.getByText('4 doctrines')).toBeVisible()
        await expect(canvas.getByText('2 doctrines')).toBeVisible()
        await expect(canvas.getByText('1 doctrine')).toBeVisible()
        const hrefs = Array.from(canvasElement.querySelectorAll('a.doctrine-card-container')).map(a => a.getAttribute('href'))
        await expect(hrefs.every(href => href?.endsWith('?location_id=60003760'))).toBe(true)
        await expect(hrefs.some(href => href?.startsWith('/ships/doctrines/12-rifter-frigate-roam/'))).toBe(true)
    },
}

export const SingleLocationNoReel = {
    args: { non_active_doctrine_location_ui: [] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelectorAll('a.doctrine-card-container')).toHaveLength(4)
        await expect(within(canvasElement).queryByText('2 doctrines')).toBeNull()
    },
}

export const AllLocations = {
    args: { active_doctrine_location_ui: doctrine_location_all, non_active_doctrine_location_ui: [doctrine_location_amamake, doctrine_location_rens] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelectorAll('a.doctrine-card-container')).toHaveLength(6)
        // The all-locations view carries no location filter on the card links.
        const hrefs = Array.from(canvasElement.querySelectorAll('a.doctrine-card-container')).map(a => a.getAttribute('href'))
        await expect(hrefs.some(href => href?.includes('location_id'))).toBe(false)
        await expect(within(canvasElement).getByText('6 doctrines')).toBeVisible()
    },
}

export const NoDoctrinesAtLocation = {
    args: { active_doctrine_location_ui: doctrine_location_empty, non_active_doctrine_location_ui: [doctrine_location_amamake] },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelectorAll('a.doctrine-card-container')).toHaveLength(0)
        await expect(within(canvasElement).getByText('0 doctrines')).toBeVisible()
        await expect(within(canvasElement).getByText('4 doctrines')).toBeVisible()
    },
}
