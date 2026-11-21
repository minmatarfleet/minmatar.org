import { expect, within } from 'storybook/test'
import ButtonStack from '@components/blocks/ButtonStack.astro'
import Button from '@components/blocks/Button.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/ButtonStack',
    component: ButtonStack,
    parameters: {
        docs: {
            description: {
                component: [
                    'Stacks buttons or links vertically with `--space-2xs` between them and makes each one as wide as the widest. Use it for action columns (a card footer, a dialog) where staggered button widths look ragged.',
                    'It has no props: it is a `Flexblock` that is `fit-content` wide, and its `<button>`/`<a>` children are forced to 100% width.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {},
    args: { slots: { default: buttons() } },
}

function buttons() {
    return [
        { component: Button, props: { color: 'fleet-red' }, slots: { default: 'Join fleet' } },
        { component: Button, props: { color: 'alliance-blue' }, slots: { default: 'Request SRP' } },
        { component: Button, props: { color: 'transparent' }, slots: { default: 'Cancel' } },
    ]
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getAllByRole('button')).toHaveLength(3)
        await expect(canvasElement.querySelector('.button-stack')).not.toBeNull()
    },
}

export const Links = {
    args: {
        slots: {
            default: [
                { component: Button, props: { href: '/fleets/' }, slots: { default: 'Fleets' } },
                { component: Button, props: { href: '/doctrines/' }, slots: { default: 'Doctrines' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('link', { name: 'Fleets' })).toHaveAttribute('href', '/fleets/')
        await expect(canvas.getByRole('link', { name: 'Doctrines' })).toHaveAttribute('href', '/doctrines/')
    },
}

export const SingleButton = {
    args: { slots: { default: [buttons()[0]] } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getAllByRole('button')).toHaveLength(1)
    },
}

export const MixedLabelLengths = {
    args: {
        slots: {
            default: [
                { component: Button, props: { size: 'sm' }, slots: { default: 'Ok' } },
                { component: Button, props: { size: 'sm', color: 'alliance-blue' }, slots: { default: 'Submit battle report to the fleet commander' } },
            ],
        },
    },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Ok' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: /battle report/ })).toBeVisible()
    },
}
