import { describe, expect, it } from 'vitest'

import { get_issue, get_issue_slugs, get_latest_issue, ISSUES } from '@/data/warzone'

describe('warzone issue registry', () => {
    it('lists yc128-07 as the latest issue', () => {
        expect(get_latest_issue().slug).toBe('yc128-07')
        expect(get_issue('yc128-07')?.permalink_path).toBe('/warzone/yc128-07/')
        expect(get_issue_slugs()).toContain('yc128-07')
        expect(ISSUES).toHaveLength(1)
    })

    it('returns undefined for an unknown slug', () => {
        expect(get_issue('yc128-99')).toBeUndefined()
    })
})
