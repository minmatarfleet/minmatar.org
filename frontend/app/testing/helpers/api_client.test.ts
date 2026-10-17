import { afterEach, describe, expect, it, vi } from 'vitest'

import {
    api_request,
    api_response,
    api_status_is,
    format_response_detail,
} from '@helpers/api.minmatar.org/client'

const URL = 'http://app:8000/api/things/1'

function mock_fetch(...responses: (Response | Error)[]) {
    const fetch_mock = vi.fn(async () => {
        const next = responses.shift()
        if (next instanceof Error)
            throw next
        return next as Response
    })
    vi.stubGlobal('fetch', fetch_mock)
    return fetch_mock
}

function json_response(body: unknown, status = 200) {
    return new Response(JSON.stringify(body), { status })
}

async function caught(promise: Promise<unknown>) {
    try {
        await promise
    } catch (error) {
        return error as Error
    }
    throw new Error('expected a rejection')
}

describe('api_request', () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('parses the JSON body', async () => {
        mock_fetch(json_response({ id: 1 }))
        expect(await api_request(URL)).toEqual({ id: 1 })
    })

    it('returns null for 204 and empty bodies', async () => {
        mock_fetch(new Response(null, { status: 204 }), new Response('', { status: 200 }))
        expect(await api_request(URL)).toBeNull()
        expect(await api_request(URL)).toBeNull()
    })

    it('sends the token, method and JSON body', async () => {
        const fetch_mock = mock_fetch(json_response({}))
        await api_request(URL, { method: 'POST', token: 'abc', body: { a: 1 } })

        expect(fetch_mock).toHaveBeenCalledWith(URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer abc' },
            body: '{"a":1}',
        })
    })

    it('omits auth when there is no token', async () => {
        const fetch_mock = mock_fetch(json_response({}), json_response({}))
        await api_request(URL, { token: false })
        await api_request(URL)

        for (const call of fetch_mock.mock.calls) {
            expect(call[1].headers).toEqual({ 'Content-Type': 'application/json' })
            expect(call[1].method).toBe('GET')
            expect(call[1]).not.toHaveProperty('body')
        }
    })

    it('sends a raw body with its own content type', async () => {
        const fetch_mock = mock_fetch(json_response({}))
        await api_request(URL, { method: 'POST', raw_body: 'log text', content_type: 'text/plain', token: 't' })

        expect(fetch_mock.mock.calls[0][1]).toMatchObject({
            body: 'log text',
            headers: { 'Content-Type': 'text/plain', 'Authorization': 'Bearer t' },
        })
    })

    it('puts the backend detail in the error and the status in cause', async () => {
        mock_fetch(json_response({ detail: 'off_trial_required' }, 400))
        const error = await caught(api_request(URL, { error: 'Error applying' }))

        expect(error.message).toBe('Error applying: off_trial_required')
        expect(error.cause).toBe(400)
    })

    it('joins a validation detail list', async () => {
        mock_fetch(json_response({ detail: [{ msg: 'field required' }, 'too long', 3] }, 422))
        const error = await caught(api_request(URL))

        expect(error.message).toBe('field required; too long')
        expect(error.cause).toBe(422)
    })

    it('falls back to the status without leaking the URL', async () => {
        mock_fetch(new Response('<html>oops</html>', { status: 502 }), json_response({}, 500))

        for (const _ of [1, 2]) {
            const error = await caught(api_request(URL, { error: 'Error fetching thing' }))
            expect(error.message).toMatch(/^Error fetching thing: HTTP error! Status — 50[02]$/)
            expect(error.message).not.toContain('http')
            expect(typeof error.cause).toBe('number')
        }
    })

    it('keeps a network failure without a status so it reads as a timeout', async () => {
        mock_fetch(new TypeError('fetch failed'))
        const error = await caught(api_request(URL, { error: 'Error fetching thing' }))

        expect(error.message).toBe('Error fetching thing: fetch failed')
        expect(error.cause).toBeUndefined()
    })

    it('rethrows unprefixed errors unchanged', async () => {
        const network = new TypeError('fetch failed')
        mock_fetch(network)

        expect(await caught(api_request(URL))).toBe(network)
    })

    it('returns null for allowed error statuses', async () => {
        mock_fetch(json_response({ detail: 'nope' }, 404))
        expect(await api_request(URL, { allow: [403, 404] })).toBeNull()
    })

    it('prefixes JSON parse failures', async () => {
        mock_fetch(new Response('not json', { status: 200 }))
        const error = await caught(api_request(URL, { error: 'Error fetching thing' }))

        expect(error.message).toMatch(/^Error fetching thing: /)
    })
})

describe('api_response and api_status_is', () => {
    afterEach(() => {
        vi.unstubAllGlobals()
    })

    it('returns the response for allowed statuses', async () => {
        mock_fetch(json_response({ detail: 'bad', problems: [1] }, 400))
        const response = await api_response(URL, { allow: [400] })

        expect(response.status).toBe(400)
        expect(await response.json()).toEqual({ detail: 'bad', problems: [1] })
    })

    it('compares the status', async () => {
        mock_fetch(json_response({}, 200), json_response({}, 201))
        expect(await api_status_is(URL, { method: 'DELETE' })).toBe(true)
        expect(await api_status_is(URL, { method: 'POST' })).toBe(false)
    })

    it('throws like api_request', async () => {
        mock_fetch(json_response({ detail: 'Not yours' }, 403))
        const error = await caught(api_status_is(URL, { error: 'Error deleting' }))

        expect(error.message).toBe('Error deleting: Not yours')
        expect(error.cause).toBe(403)
    })
})

describe('format_response_detail', () => {
    it('pulls the error out of a stringified ESI error', () => {
        expect(format_response_detail("{'error': 'Character not found'}")).toBe('Character not found')
    })

    it('handles missing and odd details', () => {
        expect(format_response_detail(undefined)).toBeNull()
        expect(format_response_detail([])).toBeNull()
        expect(format_response_detail(42)).toBe('42')
    })
})
