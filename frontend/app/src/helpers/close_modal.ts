/**
 * Close the site-wide content modal (`show_modal`) from inside it.
 *
 * Partials loaded into the modal call it from hx-on, e.g.
 * `hx-on--after-request="if (event.detail.successful) close_modal()"`.
 * It clicks the modal's backdrop, so the `show_modal` promise settles the way
 * a backdrop click settles it (false).
 */
export function close_modal(doc: Document = document): boolean {
    const backdrop = doc.querySelector<HTMLElement>('.modal-backdrop')
    if (!backdrop)
        return false

    backdrop.click()
    return true
}
