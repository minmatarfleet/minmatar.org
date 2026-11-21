import { expect, within } from 'storybook/test'
import DoctrineCard from '@components/blocks/DoctrineCard.astro'
import { in_column, type PlayArgs } from './_helpers'
import {
    doctrine_hurricane_strategic, doctrine_rifter_nonstrategic, doctrine_vargur_capital,
    doctrine_svipul_experimental, doctrine_long_name,
} from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/DoctrineCard',
    component: DoctrineCard,
    decorators: [in_column('260px')],
    parameters: {
        docs: {
            description: {
                component: 'The picture card for a doctrine: the hull render of its first primary fitting, the doctrine name and a corner icon for its type (strategic, non-strategic, capital, experimental). A badge counts the market locations when a doctrine is stocked in more than one. It is the tile on `/ships/doctrines/` and the fleet pages. The scenarios show each doctrine type, a multi-location doctrine and an over-long name.',
            },
        },
    },
    argTypes: {
        doctrine: { control: 'object', description: 'The doctrine (`DoctrineType`); the picture is its first primary fitting.' },
        title: { control: 'text', description: 'Overrides the heading; defaults to the doctrine name.' },
        subtitle: { control: 'text', description: 'Small yellow line above the heading; the list passes the primary ship names.' },
    },
    args: { doctrine: doctrine_rifter_nonstrategic, subtitle: 'Rifter' },
}

export const NonStrategic = {
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Rifter Frigate Roam')
        await expect(canvas.getByText('Rifter')).toBeVisible()
        await expect(canvasElement.querySelector('.doctrine-type-icon [data-tippy-content]')?.getAttribute('data-tippy-content')).toBe('Non strategic')
        // One location: no count badge.
        await expect(canvasElement.querySelector('h3 [data-tippy-content]')).toBeNull()
    },
}

export const StrategicMultipleLocations = {
    args: { doctrine: doctrine_hurricane_strategic, subtitle: 'Hurricane and Hurricane Fleet Issue' },
    play: async ({ canvasElement }: PlayArgs) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { level: 3 })).toHaveTextContent('Hurricane Autocannon Fleet')
        await expect(canvasElement.querySelector('.doctrine-type-icon [data-tippy-content]')?.getAttribute('data-tippy-content')).toBe('Strategic')
        const badge = canvasElement.querySelector('h3 [data-tippy-content]') as HTMLElement
        await expect(badge.getAttribute('data-tippy-content')).toBe('This doctrine is available in multiple market locations.')
        await expect(badge).toHaveTextContent('2')
    },
}

export const Capital = {
    args: { doctrine: doctrine_vargur_capital, subtitle: 'Vargur' },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByRole('heading', { level: 3 })).toHaveTextContent('Vargur Hammer')
        await expect(canvasElement.querySelector('.doctrine-type-icon [data-tippy-content]')?.getAttribute('data-tippy-content')).toBe('Capital ships')
    },
}

export const ExperimentalThreeLocations = {
    args: { doctrine: doctrine_svipul_experimental, subtitle: 'Svipul and Cynabal' },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(canvasElement.querySelector('.doctrine-type-icon [data-tippy-content]')?.getAttribute('data-tippy-content')).toBe('Experimental')
        await expect(canvasElement.querySelector('h3 [data-tippy-content]')).toHaveTextContent('3')
    },
}

export const LongName = {
    args: { doctrine: doctrine_long_name, subtitle: undefined },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByRole('heading', { level: 3 })).toHaveTextContent(doctrine_long_name.name)
    },
}

export const TitleOverride = {
    args: { title: 'Homedefense Brawlers', subtitle: 'Rifter' },
    play: async ({ canvasElement }: PlayArgs) => {
        await expect(within(canvasElement).getByRole('heading', { level: 3 })).toHaveTextContent('Homedefense Brawlers')
    },
}
