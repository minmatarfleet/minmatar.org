import { expect, within } from 'storybook/test'
import PageActions from '@components/page/PageActions.astro'
import Button from '@components/blocks/Button.astro'
import FlagIcon from '@components/icons/FlagIcon.astro'

export default {
    title: 'Page/PageActions',
    component: PageActions,
    parameters: {
        docs: {
            description: {
                component: [
                    'The row of buttons on the right of a page header. Alpine moves the rendered row into `#mobile-actions` below the `xl` breakpoint and shrinks `lg` buttons to `sm` there.',
                    'Do not wrap the slot in `x-if`/`x-teleport`: the node is moved after it initialises so its own Alpine state survives. In Storybook there is no `#mobile-actions` target, so the row always stays in place.',
                    'Extra attributes and `class` go on the inner `FlexInline` (`page-actions-slot`).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        class: { control: 'text', description: 'Extra classes for the actions row.' },
    },
    args: {
        slots: {
            default: [
                { component: Button, props: { href: '/fleets/92221/join/' }, slots: { default: 'Join fleet' } },
                { component: Button, props: { color: 'transparent' }, slots: { default: 'Copy fleet link' } },
            ],
        },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Join fleet' })).toHaveAttribute('href', '/fleets/92221/join/')
        await expect(canvas.getByRole('button', { name: 'Copy fleet link' })).toBeVisible()
        await expect(canvasElement.querySelector('.page-actions')).not.toBeNull()
    },
}

export const SlotMarkup = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const slot = canvasElement.querySelector('.page-actions-slot')
        await expect(slot).not.toBeNull()
        await expect(slot?.getAttribute('x-ref')).toBe('actions')
        await expect(slot?.parentElement?.getAttribute('x-ref')).toBe('desktop_actions')
        await expect(slot?.querySelectorAll('.button').length).toBe(2)
    },
}

export const FleetCommanderActions = {
    args: {
        slots: {
            default: [
                { component: Button, props: { color: 'alliance-blue' }, slots: { default: 'Start fleet' } },
                { component: Button, props: { color: 'transparent' }, slots: { default: 'Edit' } },
                { component: Button, props: { color: 'fleet-red' }, slots: { icon: { component: FlagIcon, props: { size: 18 } }, default: 'Cancel fleet' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('button')).toHaveLength(3)
        await expect(canvas.getByRole('button', { name: /Cancel fleet/ }).querySelector('svg')).not.toBeNull()
    },
}

export const SmallButtons = {
    args: {
        slots: {
            default: [
                { component: Button, props: { size: 'sm' }, slots: { default: 'File SRP' } },
                { component: Button, props: { size: 'sm', color: 'transparent' }, slots: { default: 'Doctrine' } },
            ],
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'File SRP' })).toHaveAttribute('data-size', 'sm')
    },
}

export const SingleAction = {
    args: {
        slots: { default: [{ component: Button, props: { href: '/fleets/upcoming/' }, slots: { default: 'Upcoming fleets' } }] },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getAllByRole('link')).toHaveLength(1)
    },
}

export const ExtraClassAndAttributes = {
    args: { class: 'justify-end', 'data-testid': 'actions-row' },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const row = within(canvasElement).getByTestId('actions-row')
        await expect(row).toHaveClass('page-actions-slot')
        await expect(row).toHaveClass('justify-end')
    },
}
