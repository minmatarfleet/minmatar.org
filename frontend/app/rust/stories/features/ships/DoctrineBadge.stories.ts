import { expect, within } from 'storybook/test'
import DoctrineBadge from '@components/blocks/DoctrineBadge.astro'
import type { PlayArgs } from './_helpers'
import { doctrine_hurricane_strategic, doctrine_long_name } from '../../../fixtures/features/ships'

export default {
    title: 'Features/Ships/DoctrineBadge',
    component: DoctrineBadge,
    parameters: {
        docs: {
            description: {
                component: 'A compact link to a doctrine: the first primary hull icon, the doctrine name and a "Doctrine" caption. It sits in fleet cards and fleet headers (`/fleets/upcoming/<id>`) so a pilot can jump to the doctrine page. The scenarios show a normal doctrine and an over-long name.',
            },
        },
    },
    argTypes: {
        doctrine: { control: 'object', description: 'The doctrine (`DoctrineType`). The link is `/ships/doctrines/<id>-<slug>/` and the icon is the first primary fitting\'s hull.' },
    },
    args: { doctrine: doctrine_hurricane_strategic },
}

export const Default = {
    play: async ({ canvasElement }: PlayArgs) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link.getAttribute('href')).toBe('/ships/doctrines/31-hurricane-autocannon-fleet/')
        await expect(link).toHaveTextContent('Hurricane Autocannon Fleet')
        await expect(link).toHaveTextContent('Doctrine')
    },
}

export const LongName = {
    args: { doctrine: doctrine_long_name },
    play: async ({ canvasElement }: PlayArgs) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link.getAttribute('href')).toMatch(/^\/ships\/doctrines\/77-/)
        await expect(link).toHaveTextContent(doctrine_long_name.name)
    },
}
