import { expect, userEvent, within } from 'storybook/test'
import SkipToContent from '@components/blocks/SkipToContent.astro'

export default {
    title: 'Components/Feedback/SkipToContent',
    component: SkipToContent,
    parameters: {
        docs: {
            description: {
                component: [
                    'The first focusable element on every page: an accessible "Skip to content" link that jumps past the header and neocom to the element with `id="content"`.',
                    'It is a `Button` link wrapped in `.skip-content`, which the layout styles to stay out of sight until it receives keyboard focus. Layouts must keep `id="content"` on the main region, or the link goes nowhere.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {},
    args: {},
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: /^skip/i })
        await expect(link).toHaveAttribute('href', '#content')
    },
}

export const KeyboardFocus = {
    name: 'Reached with Tab',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link', { name: /^skip/i })
        await userEvent.tab()
        await expect(link).toHaveFocus()
    },
}

export const Wrapper = {
    name: 'Wrapper hook for the layout styles',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link.closest('.skip-content')).not.toBeNull()
        await expect(link).toHaveClass('button')
    },
}

export const LinkIsNotANewTab = {
    name: 'Stays in the page',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const link = within(canvasElement).getByRole('link')
        await expect(link).not.toHaveAttribute('target')
        await expect(link).not.toHaveAttribute('rel')
    },
}
