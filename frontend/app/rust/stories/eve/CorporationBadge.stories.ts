import { expect, within } from 'storybook/test'
import CorporationBadge from '@components/blocks/CorporationBadge.astro'
import { EVE } from '../_controls'

const logo = (size: number) => `https://images.evetech.net/corporations/${EVE.corporation_id}/logo?size=${size}`
const corp = (extra = {}) => ({ id: EVE.corporation_id, name: EVE.corporation_name, ...extra })

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'EVE/CorporationBadge',
    component: CorporationBadge,
    parameters: {
        docs: {
            description: {
                component: [
                    'Corporation logo with its name beside it. The default slot renders under the name at every size (a ticker, a role, a count); at `lg` it replaces the description line.',
                    'Always pass `corporation.name`: without it the component fetches the name from ESI while rendering, which a page can afford but Storybook cannot. `size` lives on the `corporation` object (`xs` 24px, `sm` 32px, `lg` 64px). With `show_modal` the whole badge becomes one link to the corporation page (`/alliance/corporations/<name-slug>/`).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporation: { control: 'object', description: '`{ id, name?, size?: xs | sm | lg, description? }`. `description` shows under the name at `lg` when the slot is empty.' },
        border: { control: 'boolean', description: 'Border around the logo.' },
        highlight: { control: 'boolean', description: 'Colour the name with `--highlight`.' },
        show_modal: { control: 'boolean', description: 'Wrap the badge in a link to the corporation detail page.' },
    },
    args: {
        corporation: corp(),
        border: false,
        highlight: true,
        show_modal: false,
        slots: { default: '<small>A-RAT</small>' },
    },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
        await expect(canvas.getByText(EVE.corporation_ticker)).toBeVisible()
        const img = canvasElement.querySelector('img') as HTMLElement
        // sm: 32px logo requested at 32.
        await expect(img).toHaveAttribute('src', logo(32))
        await expect(img).toHaveAttribute('width', '32')
        await expect(canvasElement.querySelector('a')).toBeNull()
    },
}

export const ExtraSmall = {
    args: { corporation: corp({ size: 'xs' }) },
    play: async ({ canvasElement }: Ctx) => {
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('width', '24')
        await expect(img).toHaveAttribute('src', logo(32))
        await expect(within(canvasElement).getByText(EVE.corporation_ticker)).toBeVisible()
    },
}

export const Large = {
    args: { corporation: corp({ size: 'lg', description: 'Industry and logistics' }), slots: {} },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const img = canvasElement.querySelector('img') as HTMLElement
        await expect(img).toHaveAttribute('width', '64')
        await expect(img).toHaveAttribute('src', logo(64))
        await expect(canvas.getByText(EVE.corporation_name)).toBeVisible()
        // Empty slot: the description fills in.
        await expect(canvas.getByText('Industry and logistics')).toBeVisible()
    },
}

export const LargeSlotReplacesDescription = {
    args: {
        corporation: corp({ size: 'lg', description: 'Industry and logistics' }),
        slots: { default: '<small>[A-RAT] 214 members</small>' },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('[A-RAT] 214 members')).toBeVisible()
        await expect(canvas.queryByText('Industry and logistics')).toBeNull()
    },
}

export const LinkedToCorporationPage = {
    args: { show_modal: true },
    play: async ({ canvasElement }: Ctx) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link).toHaveAttribute('href', '/alliance/corporations/rattini-tribe/')
        await expect(link).toHaveTextContent(EVE.corporation_name)
        await expect(link).toHaveTextContent(EVE.corporation_ticker)
    },
}

export const BorderedNoHighlight = {
    args: { border: true, highlight: false },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('picture')).toHaveClass('border')
        const name = within(canvasElement).getByText(EVE.corporation_name)
        await expect(name.className).not.toContain('--highlight')
    },
}

export const NoSlot = {
    args: { slots: {} },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText(EVE.corporation_name)).toBeVisible()
        await expect(within(canvasElement).queryByText(EVE.corporation_ticker)).toBeNull()
    },
}
