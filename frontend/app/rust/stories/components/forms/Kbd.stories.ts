import { expect, within } from 'storybook/test'
import Kbd from '@components/blocks/Kbd.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/Kbd',
    component: Kbd,
    parameters: {
        docs: {
            description: {
                component: 'An inline keyboard-key chip for shortcut hints ("press Esc to close"). It is a bare `<kbd>` with no props; the slot is the key label. Use one chip per key and put the separator ("+") in the surrounding text.',
            },
        },
    },
    argTypes: {},
    args: { slots: { default: 'Esc' } },
}

export const Default = {
    play: async ({ canvasElement }: Ctx) => {
        const key = canvasElement.querySelector('kbd') as HTMLElement
        await expect(key).toHaveTextContent('Esc')
        await expect(key).toBeVisible()
    },
}

export const Modifier = {
    args: { slots: { default: 'Ctrl' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelectorAll('kbd')).toHaveLength(1)
        await expect(within(canvasElement).getByText('Ctrl')).toBeVisible()
    },
}

export const LongLabel = {
    args: { slots: { default: 'Page Down' } },
    play: async ({ canvasElement }: Ctx) => {
        const key = within(canvasElement).getByText('Page Down')
        await expect(key.tagName).toBe('KBD')
    },
}

export const Symbol = {
    args: { slots: { default: '/' } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('/').tagName).toBe('KBD')
    },
}
