import { describe, expect, it } from 'vitest'

import {
    corporations_with_open_application,
    open_application_elsewhere_message,
} from '@helpers/corporations/open_application'

describe('corporations_with_open_application', () => {
    const corporations = [
        { corporation_id: 1, corporation_name: 'First' },
        { corporation_id: 2, corporation_name: 'Second' },
    ]

    it('leaves the list unchanged when there is no open application', () => {
        expect(corporations_with_open_application(corporations, null)).toEqual(
            corporations,
        )
    })

    it('marks every corporation except the one with the open application', () => {
        expect(
            corporations_with_open_application(corporations, {
                corporation_id: 1,
                corporation_name: 'First',
            }),
        ).toEqual([
            { corporation_id: 1, corporation_name: 'First' },
            {
                corporation_id: 2,
                corporation_name: 'Second',
                open_application_corporation_name: 'First',
            },
        ])
    })
})

describe('open_application_elsewhere_message', () => {
    it('inserts the corporation name without treating $ as a replacement', () => {
        expect(
            open_application_elsewhere_message(
                'Open application to {corporation}.',
                'Corp $& Co',
            ),
        ).toBe('Open application to Corp $& Co.')
    })
})
