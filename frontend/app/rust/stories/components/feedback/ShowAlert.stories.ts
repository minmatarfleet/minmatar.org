import { expect, waitFor, within } from 'storybook/test'
import ShowAlert from '@components/blocks/ShowAlert.astro'

// On the site the body's Alpine scope owns `show_alert_dialog`. Rust's body does not, so the story defines the
// same-named global and records the calls; otherwise Alpine would throw a ReferenceError from `x-init`.
const calls: any[] = ((globalThis as any).__rust_alerts = (globalThis as any).__rust_alerts ?? [])
;(globalThis as any).show_alert_dialog = (alert: any) => { calls.push(alert) }

const alert_calls = () => (globalThis as any).__rust_alerts as any[]

export default {
    title: 'Components/Feedback/ShowAlert',
    component: ShowAlert,
    parameters: {
        docs: {
            description: {
                component: [
                    'Opens the site\'s alert dialog when the page loads. It renders an empty `<div>` whose Alpine `x-init` calls `show_alert_dialog(alert)` and then removes itself; pages render it conditionally (`{alert && <ShowAlert alert={alert} />}`) to report the result of a server action.',
                    'It has no visible output of its own. The alert may carry a `partial` to load into the dialog and `hx` options to submit it. The story stubs `show_alert_dialog`, because the real one lives on the layout\'s body.',
                ].join('\n\n'),
            },
        },
        rust: { allow_empty: true },
    },
    argTypes: {
        alert: { control: 'object', description: '`{ title, content, partial?, hx? }` passed to `show_alert_dialog`.' },
    },
    args: {
        alert: { title: 'Fleet created', content: 'Your Strategic fleet is now on the schedule.' },
    },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await waitFor(() => expect(alert_calls().some((a) => a.title === 'Fleet created')).toBe(true))
        // The marker removes itself once it has fired.
        await waitFor(() => expect(canvasElement.querySelector('[x-init]')).toBeNull())
        await expect(within(canvasElement).queryByRole('alert')).toBeNull()
    },
}

export const ErrorMessage = {
    args: { alert: { title: 'SRP request failed', content: 'Killmail 134521998 does not belong to your characters.' } },
    play: async () => {
        await waitFor(() => {
            const last = alert_calls().find((a) => a.title === 'SRP request failed')
            expect(last?.content).toContain('134521998')
        })
    },
}

export const WithPartial = {
    name: 'With a partial',
    args: {
        alert: {
            title: 'Pick a doctrine',
            content: 'Choose the fit you will fly.',
            partial: '/partials/doctrine_picker_component',
        },
    },
    play: async () => {
        await waitFor(() => {
            const sent = alert_calls().find((a) => a.title === 'Pick a doctrine')
            expect(sent?.partial).toBe('/partials/doctrine_picker_component')
        })
    },
}

export const WithHtmxSubmit = {
    name: 'With htmx options',
    args: {
        alert: {
            title: 'Leave this fleet?',
            content: 'You will lose your place in the roster.',
            hx: { method: 'post', url: '/partials/fleet_leave_component' },
        },
    },
    play: async () => {
        await waitFor(() => {
            const sent = alert_calls().find((a) => a.title === 'Leave this fleet?')
            expect(sent?.hx?.method).toBe('post')
        })
    },
}
