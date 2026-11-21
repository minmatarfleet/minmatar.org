import { expect, waitFor, within } from 'storybook/test'
import ErrorRefetch from '@components/blocks/ErrorRefetch.astro'

// `args.error` is a real `Error` on the site; stories pass the same shape as a plain object, which is all the
// component reads (`message`, and `cause` as a number for an HTTP status).
const error = (message: string, cause?: number) => ({ message, ...(cause !== undefined ? { cause } : {}) })

const loading = (canvasElement: HTMLElement) => canvasElement.querySelector('.loading') as HTMLElement

export default {
    title: 'Components/Feedback/ErrorRefetch',
    component: ErrorRefetch,
    parameters: {
        docs: {
            description: {
                component: [
                    'What a server-rendered partial shows when its API call failed: the error message plus a self-retrying loader that re-requests the partial (`hx-get`) and swaps the result in place of itself.',
                    '`args.delay` is the wait before this attempt (0 = retry as soon as the block is visible, `intersect once`); each retry asks for `delay + RETRYING_TIME_INCREMENT_SECONDS`, and past `MAX_RETRYING_TIME_SECONDS` it gives up with "too many tries". An HTTP-status `cause` is treated as a real error, so no retry is scheduled.',
                    'Use `target` to swap into a specific element instead of the block itself. Empty (successful) lists use `EmptyState`, not this.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        args: {
            control: 'object',
            description: '`{ partial, error, delay, target? }`: the partial path to refetch, the failure, seconds waited so far, and an optional CSS selector to swap into.',
        },
        animation: { control: 'boolean', description: 'Reserved for the loading animation; currently unused by the markup.' },
    },
    args: {
        args: {
            partial: '/partials/fleet_schedule_component',
            error: error('Could not load the fleet schedule.'),
            delay: 0,
        },
        animation: true,
    },
}

export const Default = {
    name: 'Retry immediately (delay 0)',
    parameters: { htmx: { '/partials/fleet_schedule_component': { body: '<p>Fleet schedule loaded</p>', delay: 300 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/Could not load the fleet schedule/)).toBeVisible()
        const loader = loading(canvasElement)
        await expect(loader).toHaveAttribute('hx-trigger', 'intersect once')
        await expect(loader.getAttribute('hx-get')).toContain('/partials/fleet_schedule_component')
        await expect(loader.getAttribute('hx-get')).toContain('delay=')
        await expect(loader).toHaveAttribute('hx-swap', 'outerHTML transition:true')
        await expect(loader).toHaveAttribute('hx-indicator', '.loader')
        await expect(loader.textContent?.trim()).toMatch(/now/i)
    },
}

export const CountdownRetry = {
    name: 'Retry after a delay',
    args: {
        args: { partial: '/partials/srp_requests_component', error: error('SRP requests are unavailable.'), delay: 10 },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/SRP requests are unavailable/)).toBeVisible()
        const loader = loading(canvasElement)
        await expect(loader).toHaveAttribute('hx-trigger', 'load delay:10s')
        await expect(loader.getAttribute('x-data')).toContain('countdown: 10')
        await expect(loader.textContent).toContain('10')
    },
}

export const CustomTarget = {
    name: 'Swap into a target',
    args: {
        args: {
            partial: '/partials/doctrine_list_component',
            error: error('Doctrines failed to load.'),
            delay: 0,
            target: '#doctrine-list',
        },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const loader = loading(canvasElement)
        await expect(loader.getAttribute('x-bind:hx-target')).toContain('#doctrine-list')
    },
}

export const DefaultTarget = {
    name: 'Swaps itself by default',
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const loader = loading(canvasElement)
        // Without `target`, the loader targets the block's own generated id.
        await expect(loader.getAttribute('x-bind:hx-target')).toContain('#${id}')
        await expect(loader.closest('[x-bind\\:id]')?.getAttribute('x-data')).toContain('error-refetch')
    },
}

export const ServerError = {
    name: 'HTTP error (no automatic retry)',
    args: {
        args: { partial: '/partials/fleet_schedule_component', error: error('Fleet service returned an error.', 502), delay: 0 },
    },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(within(canvasElement).getByText(/Fleet service returned an error/)).toBeVisible()
        await expect(canvasElement.querySelector('[hx-get]')).toBeNull()
        await expect(canvasElement.querySelector('.loading')).toBeNull()
    },
}

export const RetrySucceeds = {
    name: 'Retry succeeds and swaps in the partial',
    tags: ['browser'],
    parameters: { htmx: { '/partials/fleet_schedule_component': { body: '<p>Fleet schedule loaded</p>', delay: 400 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText(/Could not load the fleet schedule/)).toBeVisible()
        await waitFor(() => expect(canvas.getByText('Fleet schedule loaded')).toBeVisible(), { timeout: 4000 })
        await expect(canvas.queryByText(/Could not load/)).toBeNull()
        await expect((window as any).__rust_htmx_requests.some((r: any) => r.url.startsWith('/partials/fleet_schedule_component'))).toBe(true)
    },
}

export const RetryStillFailing = {
    name: 'Retry fails again',
    tags: ['browser'],
    parameters: { htmx: { '/partials/fleet_schedule_component': { status: 500, body: '', delay: 300 } } },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await waitFor(() => expect((window as any).__rust_htmx_requests.some((r: any) => r.url.startsWith('/partials/fleet_schedule_component'))).toBe(true), { timeout: 4000 })
        // A failed retry does not swap: the message and loader stay.
        await new Promise((resolve) => setTimeout(resolve, 600))
        await expect(canvas.getByText(/Could not load the fleet schedule/)).toBeVisible()
    },
}
