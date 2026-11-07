/**
 * Drag-to-order for a manage list, with up/down buttons as the fallback.
 * Local UI only: it moves the rendered rows (and the hidden inputs inside
 * them), then fires `event` on the row so the page can save the new order
 * (an htmx trigger) or leave it for the form's Save.
 *
 *   <ol x-data="{ dragging: null }">
 *       <li {...sort_item_attrs('guides-reordered')}>
 *           <span {...sort_handle_attrs}>⋮⋮</span> ...
 *           <button type="button" {...sort_up_attrs('guides-reordered')}>Up</button>
 *       </li>
 *   </ol>
 *
 * Items are siblings marked `data-sort-item`; the container holds the
 * `dragging` state.
 */

const ITEM = '[data-sort-item]'

/** Attributes for each sortable item (a <li>, or an ExpandRow <tbody>). */
export const sort_item_attrs = (event: string): Record<string, string> => ({
    'data-sort-item': '',
    'x-on:dragstart': "dragging = $el; $event.dataTransfer.effectAllowed = 'move'",
    'x-on:dragover.prevent': `
        if (!dragging || dragging === $el || dragging.parentNode !== $el.parentNode) return
        const box = $el.getBoundingClientRect()
        $el.parentNode.insertBefore(dragging, $event.clientY - box.top > box.height / 2 ? $el.nextSibling : $el)
    `,
    'x-on:dragend': `$el.draggable = false; if (dragging) { dragging = null; $dispatch('${event}') }`,
})

/** The grip: only it starts a drag, so text in an open row stays selectable. */
export const sort_handle_attrs: Record<string, string> = {
    'x-on:pointerdown': `$el.closest('${ITEM}').draggable = true`,
    'x-on:pointerup': `$el.closest('${ITEM}').draggable = false`,
    'aria-hidden': 'true',
}

/** A "move up" button. */
export const sort_up_attrs = (event: string): Record<string, string> => ({
    type: 'button',
    'x-on:click': `
        const item = $el.closest('${ITEM}'), before = item.previousElementSibling
        if (before && before.matches('${ITEM}')) { item.parentNode.insertBefore(item, before); $el.focus(); $dispatch('${event}') }
    `,
})

/** A "move down" button. */
export const sort_down_attrs = (event: string): Record<string, string> => ({
    type: 'button',
    'x-on:click': `
        const item = $el.closest('${ITEM}'), after = item.nextElementSibling
        if (after && after.matches('${ITEM}')) { item.parentNode.insertBefore(after, item); $el.focus(); $dispatch('${event}') }
    `,
})
