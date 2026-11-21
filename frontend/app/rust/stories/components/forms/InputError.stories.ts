import { expect, within } from 'storybook/test'
import InputError from '@components/blocks/InputError.astro'
import Input from '@components/blocks/Input.astro'

type Ctx = { canvasElement: HTMLElement }

export default {
    title: 'Components/Forms/InputError',
    component: InputError,
    parameters: {
        docs: {
            description: {
                component: [
                    'Wraps a field and overlays a warning marker at its right edge while an Alpine expression is true. Hovering the marker shows the error text in a tippy tooltip. Both props are Alpine expressions (strings), evaluated in the parent `x-data` scope, not values.',
                    'Wrap the form in an `x-data` that owns the field and its error. The marker is `x-show`-hidden when `show_prop` is false, so the field looks untouched. Use it with `Input`; for form-level failures use a `ShowAlert` instead.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        show_prop: { control: 'text', description: 'Alpine expression: show the marker while truthy.' },
        error_prop: { control: 'text', description: 'Alpine expression whose value is the tooltip text. The tooltip re-initialises whenever it changes.' },
    },
    args: {
        // Real pages pass names from the enclosing x-data (`show_prop="errors.link"`); the stories pass literals so they need no wrapper.
        show_prop: 'true',
        error_prop: "'That is not a zKillboard link.'",
        slots: { default: field() },
    },
}

export const NoError = {
    args: { show_prop: 'false' },
    play: async ({ canvasElement }: Ctx) => {
        const marker = canvasElement.querySelector('span[x-show]') as HTMLElement
        await expect(marker).not.toBeNull()
        await expect(marker).not.toBeVisible()
        await expect(within(canvasElement).getByPlaceholderText('zKillboard link')).toBeVisible()
    },
}

export const WithError = {
    play: async ({ canvasElement }: Ctx) => {
        const marker = canvasElement.querySelector('span[x-show]') as HTMLElement
        await expect(marker).toBeVisible()
        await expect(marker).toHaveAttribute('data-tippy-content', 'That is not a zKillboard link.')
        await expect(marker).toHaveTextContent('⚠️')
    },
}

export const ErrorOnSmallInput = {
    args: {
        error_prop: "'Tickers are 3-5 characters.'", slots: { default: field({ size: 'sm', placeholder: 'Ticker', id: 'ticker' }) } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByPlaceholderText('Ticker')).toHaveAttribute('data-size', 'sm')
        await expect(canvasElement.querySelector('span[x-show]')).toHaveAttribute('data-tippy-content', 'Tickers are 3-5 characters.')
    },
}

export const BoundExpressions = {
    name: 'Expressions are bound, not literal',
    play: async ({ canvasElement }: Ctx) => {
        const marker = canvasElement.querySelector('span[x-show]') as HTMLElement
        await expect(marker).toHaveAttribute('x-show', 'true')
        await expect(marker).toHaveAttribute('x-bind:data-tippy-content', "'That is not a zKillboard link.'")
        await expect(marker.getAttribute('x-effect')).toContain("'That is not a zKillboard link.' && init_tippy()")
    },
}

function field(props: Record<string, unknown> = {}) {
    return {
        component: Input,
        props: { id: 'killmail', name: 'killmail', placeholder: 'zKillboard link', ...props },
    }
}
