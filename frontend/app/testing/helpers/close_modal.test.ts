import { expect, test, vi } from 'vitest'
import { close_modal } from '@helpers/close_modal'

test('close_modal clicks the modal backdrop', () => {
    const click = vi.fn()
    const doc = { querySelector: (selector: string) => selector === '.modal-backdrop' ? { click } : null } as unknown as Document

    expect(close_modal(doc)).toBe(true)
    expect(click).toHaveBeenCalledOnce()
})

test('close_modal does nothing without a modal', () => {
    const doc = { querySelector: () => null } as unknown as Document

    expect(close_modal(doc)).toBe(false)
})
