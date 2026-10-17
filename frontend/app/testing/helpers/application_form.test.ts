import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'

import {
    corporationApplicationAlpineState,
    l3arnApplicationAlpineState,
} from '@helpers/corporations/application_form'
import { L3ARN_APPLICATION_DRAFT_STORAGE_KEY } from '@helpers/corporations/l3arn_application'

// Captured from the two hand-written builders before they were merged.
const fixture = (name: string) =>
    readFileSync(`testing/helpers/fixtures/application_alpine_state/${name}.txt`, 'utf8')

describe('application Alpine state matches the pre-merge builders byte for byte', () => {
    it.each([
        ['corporation_dialog', () => corporationApplicationAlpineState(true)],
        ['corporation_inline', () => corporationApplicationAlpineState(false)],
        ['l3arn_dialog', () => l3arnApplicationAlpineState(true)],
        ['l3arn_inline', () => l3arnApplicationAlpineState(false)],
    ])('%s', (name, build) => {
        expect(build()).toBe(fixture(name))
    })
})

// Evaluate the state like Alpine does (a plain object literal).
function state(source: string): Record<string, any> {
    return new Function(`return (${source})`)()
}

function fill(form: Record<string, any>, answer_field: string) {
    form.introduction = 'Hello'
    form.activity_region = 'EU'
    form.activity_period = 'evening'
    form.user_timezone = 'Europe/Berlin'
    form.roles = ['fleet_damage']
    form[answer_field] = 'Shield kites'
    form.how_found = 'reddit_post_seen'
    form.agree_tenets = true
    form.confirm_auth_chars = true
}

describe('application Alpine state behaviour', () => {
    beforeEach(() => sessionStorage.clear())
    afterEach(() => sessionStorage.clear())

    it('corporation form: ready only once every required answer is in', () => {
        const form = state(corporationApplicationAlpineState(false))
        expect(form.answersReady()).toBe(false)
        fill(form, 'doctrines')
        expect(form.answersReady()).toBe(true)
        expect(form.timezone).not.toBe('')
        form.roles = ['not-a-role']
        expect(form.answersReady()).toBe(false)
        const payload = form.buildDescriptionPayload()
        expect(payload.corp_application).toBe(true)
        expect(payload).not.toHaveProperty('l3arn')
        expect(payload.doctrines).toBe('Shield kites')
    })

    it('L3ARN form: needs the omega confirmation and keeps a session draft', () => {
        const form = state(l3arnApplicationAlpineState(false))
        fill(form, 'goals')
        expect(form.answersReady()).toBe(false)
        form.confirm_omega = true
        expect(form.answersReady()).toBe(true)

        form.updateApplicationStatus()
        const saved = JSON.parse(sessionStorage.getItem(L3ARN_APPLICATION_DRAFT_STORAGE_KEY) as string)
        expect(saved.l3arn).toBe(true)
        expect(saved.goals).toBe('Shield kites')

        const restored = state(l3arnApplicationAlpineState(false))
        restored.initL3arnForm()
        expect(restored.goals).toBe('Shield kites')
        expect(restored.confirm_omega).toBe(true)

        restored.clearL3arnForm()
        expect(restored.goals).toBe('')
        // Clearing re-detects the region and timezone, which are saved again.
        const after_clear = JSON.parse(sessionStorage.getItem(L3ARN_APPLICATION_DRAFT_STORAGE_KEY) as string)
        expect(after_clear.goals).toBe('')
        expect(after_clear.confirm_omega).toBe(false)
    })

    it('L3ARN form counts listed corporations against the Discord budget', () => {
        const form = state(l3arnApplicationAlpineState(false))
        expect(form.descriptionWithinLimit()).toBe(true)
        form.other_corporations = ['x'.repeat(2000)]
        expect(form.descriptionWithinLimit()).toBe(false)
    })
})
