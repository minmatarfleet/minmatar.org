import { expect, within } from 'storybook/test'
import Hero from '@components/blocks/Hero.astro'
import Button from '@components/blocks/Button.astro'
import Tag from '@components/blocks/Tag.astro'
import { EVE, radio_control } from '../_controls'

type Ctx = { canvasElement: HTMLElement }

const meta_row = [
    { component: Tag, props: { color: 'alliance-blue', text: EVE.corporation_ticker } },
    `<small>${EVE.alliance_name}</small>`,
    '<small>Founded March 2019</small>',
]

const actions = [
    { component: Button, props: { color: 'transparent', href: '/discord/' }, slots: { default: 'Discord' } },
    { component: Button, props: { href: '/apply/' }, slots: { default: 'Apply' } },
]

export default {
    title: 'Page/Hero',
    component: Hero,
    parameters: {
        docs: {
            description: {
                component: [
                    'The page masthead: an image, the title as the landing heading, a meta row and actions on the right. It is the structure of the corporation page and the manage screens, with their differences as props. It is not the cover hero of a landing tile or the fleet header; those have their own layout.',
                    'Slots: `meta` is the badge and fact row under the title, `actions` takes at most one red `Button` plus quiet `color="transparent"` links (full width on a phone), and the default slot is a body under the meta row. `variant="compact"` drops the title to page-title size and the image to a badge. The image is decorative by default (`image_alt` empty), since the title names it.',
                    '`meta_gap` and `meta_size` set the meta row\'s gap and font size (`inherit` leaves the size to the items), `actions_align` aligns the actions on the cross axis and `actions_id` gives the group an id so a link can scroll to it.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        title: { control: 'text', description: 'The page name, as the landing `<h1>` (a link to the page by default).' },
        eyebrow: { control: 'text', description: 'A small label above the title.' },
        image: { control: 'text', description: 'Image URL: a corp logo, a type icon. Omitted when the page is about no one thing.' },
        image_alt: { control: 'text', description: 'Alt text; empty (decorative) by default.' },
        variant: radio_control(['default', 'compact'] as const, '`compact` is the smaller masthead for cards and nested pages.'),
        path: { control: 'text', description: 'Title link target; defaults to the current page.' },
        meta_gap: { control: 'text', description: 'Gap in the meta row, a CSS gap value.' },
        meta_size: { control: 'text', description: 'Font size of the meta row; `inherit` leaves it to the items.' },
        actions_align: radio_control(['center', 'flex-start'] as const, 'Cross-axis alignment of the actions.'),
        actions_id: { control: 'text', description: 'id for the actions group.' },
    },
    args: {
        title: EVE.corporation_name,
        image: `https://images.evetech.net/corporations/${EVE.corporation_id}/logo?size=128`,
        variant: 'default',
        path: '/alliance/corporations/rattini-tribe/',
        meta_gap: 'var(--space-3xs) var(--space-xs)',
        meta_size: 'var(--step--1)',
        actions_align: 'center',
        slots: { meta: meta_row, actions },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const heading = canvas.getByRole('heading', { level: 1, name: EVE.corporation_name })
        await expect(heading).toHaveClass('is-landing')
        await expect(within(heading).getByRole('link')).toHaveAttribute('href', '/alliance/corporations/rattini-tribe/')
        const image = canvasElement.querySelector('img') as HTMLImageElement
        await expect(image).toHaveAttribute('alt', '')
        await expect(image).toHaveAttribute('width', '128')
        await expect(canvas.getByText(EVE.corporation_ticker)).toBeVisible()
        await expect(canvas.getByText('Founded March 2019')).toBeVisible()
        await expect(canvas.getByRole('link', { name: 'Apply' })).toHaveAttribute('href', '/apply/')
        await expect(canvas.getByRole('link', { name: 'Discord' })).toBeVisible()
    },
}

export const Compact = {
    args: { variant: 'compact' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.firstElementChild).toHaveClass('hero--compact')
        await expect(within(canvasElement).getByRole('heading', { level: 1 })).not.toHaveClass('is-landing')
    },
}

export const WithEyebrowAndBody = {
    args: {
        eyebrow: 'Industry',
        title: 'LP desk',
        image: undefined,
        slots: { meta: ['<small>4 corporations</small>'], default: '<p>Orders waiting for a builder, newest first.</p>', actions: [actions[1]] },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Industry')).toBeVisible()
        await expect(canvas.getByText('Orders waiting for a builder, newest first.')).toBeVisible()
        await expect(canvasElement.querySelector('img')).toBeNull()
    },
}

export const TitleOnly = {
    args: { image: undefined, slots: {} },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('heading', { level: 1, name: EVE.corporation_name })).toBeVisible()
        await expect(canvasElement.querySelector('.hero__meta')).toBeNull()
        await expect(canvasElement.querySelector('.hero__actions')).toBeNull()
        await expect(canvasElement.querySelector('.hero__body')).toBeNull()
    },
}

export const ActionsAnchor = {
    name: 'Actions with an anchor id, top-aligned',
    args: { actions_id: 'corporation-apply', actions_align: 'flex-start', meta_size: 'inherit' },
    play: async ({ canvasElement }: Ctx) => {
        const group = canvasElement.querySelector('#corporation-apply') as HTMLElement
        await expect(group).toHaveClass('hero__actions')
        await expect(group.getAttribute('style')).toContain('--hero-actions-align: flex-start')
        await expect(canvasElement.querySelector('.hero__meta')?.getAttribute('style')).toContain('--hero-meta-size: inherit')
    },
}
