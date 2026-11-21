import { expect, within } from 'storybook/test'
import Breadcrumb from '@components/blocks/Breadcrumb.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Navigation/Breadcrumb',
    component: Breadcrumb,
    parameters: {
        docs: {
            description: {
                component: [
                    'A trail of ancestors ending at the current page, as a `<nav aria-label="Breadcrumb">` around an ordered list. The last item is the current page (`aria-current="page"`) and is never a link, even if it has an `href`.',
                    'Use it on detail pages that sit two or more levels deep (a fleet inside Fleets, a corporation inside the Alliance). Items without an `href` render as plain text. An empty `items` list renders nothing at all.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        items: { control: 'object', description: 'Trail in order, `[{ label, href? }]`. The last entry is the current page.' },
        class: { control: 'text', description: 'Extra classes on the `<nav>`.' },
    },
    args: {
        items: [
            { label: 'Fleets', href: '/fleets/' },
            { label: 'History', href: '/fleets/history/' },
            { label: 'Strategic fleet in Amamake' },
        ],
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const nav = canvas.getByRole('navigation', { name: 'Breadcrumb' })
        await expect(within(nav).getAllByRole('listitem')).toHaveLength(3)
        await expect(canvas.getByRole('link', { name: 'Fleets' })).toHaveAttribute('href', '/fleets/')
        await expect(canvas.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/fleets/history/')
        const current = canvas.getByText('Strategic fleet in Amamake')
        await expect(current).toHaveAttribute('aria-current', 'page')
        await expect(canvas.queryByRole('link', { name: 'Strategic fleet in Amamake' })).toBeNull()
    },
}

export const SingleItem = {
    name: 'Single item',
    args: { items: [{ label: 'Doctrines' }] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('listitem')).toHaveLength(1)
        await expect(canvas.getByText('Doctrines')).toHaveAttribute('aria-current', 'page')
        await expect(canvas.queryByRole('link')).toBeNull()
    },
}

export const CurrentWithHref = {
    name: 'Current page with an href is not a link',
    args: {
        items: [
            { label: 'Alliance', href: '/alliance/' },
            { label: 'Corporations', href: '/alliance/corporations/' },
        ],
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('link')).toHaveLength(1)
        await expect(canvas.getByText('Corporations')).toHaveAttribute('aria-current', 'page')
    },
}

export const MiddleWithoutHref = {
    name: 'Middle item without a link',
    args: {
        items: [
            { label: 'Alliance', href: '/alliance/' },
            { label: 'Rattini Tribe' },
            { label: 'Members' },
        ],
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('link')).toHaveLength(1)
        const middle = canvas.getByText('Rattini Tribe')
        await expect(middle.tagName).toBe('LI')
        await expect(middle).not.toHaveAttribute('aria-current')
    },
}

export const LongTrail = {
    name: 'Long trail wraps',
    args: {
        items: [
            { label: 'Industry', href: '/industry/' },
            { label: 'Products', href: '/industry/products/' },
            { label: 'Ships', href: '/industry/products/ships/' },
            { label: 'Frigates', href: '/industry/products/ships/frigates/' },
            { label: 'Minmatar frigates', href: '/industry/products/ships/frigates/minmatar/' },
            { label: 'Rifter Fleet Issue blueprint copy, 10 runs, ME 10 TE 20' },
        ],
        style: 'max-width: 24rem',
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('link')).toHaveLength(5)
        await expect(canvas.getAllByRole('listitem')).toHaveLength(6)
    },
}

export const Empty = {
    name: 'Empty (renders nothing)',
    args: { items: [] },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).queryByRole('navigation')).toBeNull()
    },
}
