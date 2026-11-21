import { expect, within } from 'storybook/test'
import SolarSystemTag from '@components/blocks/sde/SolarSystemTag.astro'
import { system } from './_fixtures'

type Ctx = { canvasElement: HTMLElement }

const root = (canvasElement: HTMLElement) => canvasElement.querySelector('.solar-system-tag') as HTMLElement

export default {
    title: 'EVE/SDE/SolarSystemTag',
    component: SolarSystemTag,
    parameters: {
        docs: {
            description: {
                component: [
                    'A solar system: name, SecurityStatus and "Constellation ‹ Region", as the site\'s system lists show them. Inline by default, for fleet locations, stagings and timers; `icon` adds the star\'s icon (the system finder layout, used by SolarSystemResults).',
                    '`href` makes the name a link (with `icon`, wrap the tag in a link instead, as SolarSystemResults does). The system comes in as a prop (`search_solar_systems()` in `helpers/sde/search.ts` returns this shape); the component never queries the SDE. `data-security-band` on the root is there for filters.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        system: { control: 'object', description: '`SdeSolarSystem`: id, name, raw security, star type, constellation and region.' },
        href: { control: 'text', description: 'Link for the system name.' },
        show_location: { control: 'boolean', description: 'Show "Constellation ‹ Region".' },
        icon: { control: 'boolean', description: 'Star icon beside the name (stacked layout).' },
        icon_size: { control: 'select', options: [32, 48, 64], description: 'Star icon width in px.' },
    },
    args: {
        system: system('Amamake'),
        show_location: true,
        icon: false,
        icon_size: 32,
    },
}

export const Default = {
    name: 'Amamake (inline)',
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Amamake')).toBeVisible()
        await expect(canvas.getByText('Hed ‹ Heimatar')).toBeVisible()
        await expect(root(canvasElement)).toHaveAttribute('data-system-id', '30002537')
        await expect(root(canvasElement)).toHaveAttribute('data-security-band', 'low')
        await expect(canvasElement.querySelector('.security-status')).toHaveAttribute('data-security', '0.4')
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const Linked = {
    args: { href: '/intel/moons/Amamake' },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link', { name: 'Amamake' })
        await expect(link).toHaveAttribute('href', '/intel/moons/Amamake')
    },
}

export const WithStarIcon = {
    name: 'With star icon (Rens)',
    args: { system: system('Rens'), icon: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Rens')).toBeVisible()
        await expect(canvas.getByText('Ortner ‹ Heimatar')).toBeVisible()
        const img = canvasElement.querySelector('img') as HTMLImageElement
        await expect(img).toHaveAttribute('src', `https://images.evetech.net/types/${system('Rens').sun_type_id}/icon?size=64`)
        await expect(img).toHaveAttribute('alt', '')
        await expect(img).toHaveAttribute('width', '32')
        await expect(root(canvasElement)).toHaveAttribute('data-security-band', 'high')
    },
}

export const WithoutLocation = {
    args: { system: system('Huola'), show_location: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('Huola')).toBeVisible()
        await expect(canvasElement.querySelector('.solar-system-tag__location')).toBeNull()
    },
}

export const NullSec = {
    name: 'Null-sec (1DQ1-A)',
    args: { system: system('1DQ1-A'), icon: true, icon_size: 48 },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('O-EIMK ‹ Delve')).toBeVisible()
        await expect(canvasElement.querySelector('.security-status')).toHaveAttribute('data-security', '-0.4')
        await expect(canvasElement.querySelector('img')).toHaveAttribute('width', '48')
    },
}

export const Wormhole = {
    name: 'J-space (J164104)',
    args: { system: system('J164104') },
    play: async ({ canvasElement }: Ctx) => {
        await expect(root(canvasElement)).toHaveAttribute('data-security-band', 'wormhole')
        await expect(within(canvasElement).getByText('C-C00119 ‹ C-R00012')).toBeVisible()
    },
}
