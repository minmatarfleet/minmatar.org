import { expect, within } from 'storybook/test'
import FittingCard from '@components/blocks/FittingCard.astro'
import { in_column, type PlayArgs } from './_helpers'
import {
    rifter_fitting, hurricane_fleet_issue_fitting, vagabond_fitting, svipul_fitting, long_name_fitting,
} from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/FittingCard',
    component: FittingCard,
    decorators: [in_column('260px')],
    parameters: {
        docs: {
            description: {
                component: 'The picture card for one ship fitting: hull render, meta-group icon (Faction, Tech II, Tech III), tag line and title, with share and copy-EFT buttons on hover. It appears in the grids on `/ships/fittings/`, on a doctrine page (`/ships/doctrines/<id>/`) and in search results. The scenarios cover each meta group, a fit with no tags and a very long fitting name.',
            },
        },
    },
    argTypes: {
        fitting: { control: 'object', description: 'The fitting (`FittingItem`): id, names, hull, meta group and the EFT text the copy button holds.' },
        title: { control: 'text', description: 'Overrides the heading; defaults to the fitting name. Doctrine tiers pass the ship name.' },
        subtitle: { control: 'text', description: 'Optional extra line passed by the caller (the fitting type on doctrine pages).' },
        tags: { control: 'object', description: 'Tag slugs, shown as a comma list above the title. Unknown slugs fall back to the slug with spaces.' },
    },
    args: { fitting: rifter_fitting, tags: rifter_fitting.tags },
}

export const Tech1Frigate = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Rifter - Amamake Brawler')
        await expect(canvas.getByText('Nanogang and New player friendly')).toBeVisible()
        await expect(canvasElement.querySelector('img')?.getAttribute('src')).toContain('587')
        // Tech I has no meta icon.
        await expect(canvasElement.querySelector('.ship-type-icon svg')).toBeNull()
    },
}

export const FactionBattlecruiser = {
    // The Faction/Tech II/Tech III corner icons carry an inline <style>; happy-dom (the vitest DOM) drops the rest of the card after it.
    tags: ['browser'],
    args: { fitting: hurricane_fleet_issue_fitting, tags: hurricane_fleet_issue_fitting.tags },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Hurricane Fleet Issue - Alpha Strike')
        await expect(canvasElement.querySelector('.ship-type-icon svg')).not.toBeNull()
        await expect(canvas.getByText('Command Bursts and Fleet composition')).toBeVisible()
    },
}

export const Tech2Cruiser = {
    // The Faction/Tech II/Tech III corner icons carry an inline <style>; happy-dom (the vitest DOM) drops the rest of the card after it.
    tags: ['browser'],
    args: { fitting: vagabond_fitting, tags: vagabond_fitting.tags },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Vagabond - Fast Pursuit')
        await expect(canvasElement.querySelector('.ship-type-icon svg')).not.toBeNull()
    },
}

export const Tech3WithShipNameTitle = {
    name: 'Tech 3, titled by ship name',
    // The Faction/Tech II/Tech III corner icons carry an inline <style>; happy-dom (the vitest DOM) drops the rest of the card after it.
    tags: ['browser'],
    args: { fitting: svipul_fitting, tags: svipul_fitting.tags, title: svipul_fitting.ship_name },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent(/^Svipul$/)
        await expect(canvas.getByText('Escape Frigate')).toBeVisible()
    },
}

export const NoTagsNoMeta = {
    args: { fitting: { ...long_name_fitting, fitting_name: 'Rifter - Roam' }, tags: undefined },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Rifter - Roam')
        await expect(canvasElement.querySelector('.ship-type-icon svg')).toBeNull()
    },
}

export const LongFittingName = {
    args: { fitting: long_name_fitting, tags: undefined },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent(long_name_fitting.fitting_name)
    },
}
