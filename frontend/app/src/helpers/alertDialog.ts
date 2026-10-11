/**
 * Keep Open's bound href until after the click's default action.
 *
 * Accept with `accept_href` is a real `<a target="_blank">`. Resetting
 * `alert_dialog_accept_href` (or closing the dialog) in the same turn
 * clears that href and the browser navigates the current tab instead.
 */
export function schedule_alert_dialog_reset(options: {
    action: string
    accept_href: string
    finish: () => void
    defer?: (callback: () => void) => void
}): void {
    const defer = options.defer ?? ((callback) => {
        setTimeout(callback, 0)
    })
    if (options.action === 'accept' && options.accept_href) {
        defer(options.finish)
        return
    }
    options.finish()
}
