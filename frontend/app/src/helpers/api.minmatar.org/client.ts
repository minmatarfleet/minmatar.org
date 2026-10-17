/**
 * The one way the server talks to the backend API.
 *
 * Every helper in `helpers/api.minmatar.org` goes through `api_request` (JSON
 * in, JSON out) or `api_response` (when it needs the raw Response). Both:
 *
 * - send `Content-Type` and, when a token is given, `Authorization: Bearer`;
 * - throw an `Error` whose `cause` is the HTTP status (ErrorRefetch reads it
 *   to tell a failed request from a timeout) and whose message is the
 *   backend's `detail`, or `HTTP error! Status — <status>` when it sent none;
 * - keep backend URLs out of the message (they are logged instead);
 * - prefix every error with `<error>: ` when an `error` label is given, so
 *   callers keep their `Error fetching fleet: ...` style messages.
 */
import { parse_error_message } from '@helpers/string'

export type ApiToken = string | false | null | undefined

export interface ApiOptions {
    /** HTTP method, `GET` by default. */
    method?:        string;
    /** Bearer token. Falsy sends no Authorization header. */
    token?:         ApiToken;
    /** JSON-encoded into the request body when not undefined. */
    body?:          unknown;
    /** Sent as is, for non-JSON uploads. Takes precedence over `body`. */
    raw_body?:      BodyInit;
    /** `application/json` by default. */
    content_type?:  string;
    /** Error message prefix, e.g. `Error fetching fleet`. */
    error?:         string;
    /** Statuses that are not errors here: `api_request` returns null for them. */
    allow?:         number[];
    signal?:        AbortSignal;
}

export function api_headers(token?:ApiToken, content_type:string = 'application/json') {
    const headers:Record<string, string> = {
        'Content-Type': content_type,
    }

    if (token)
        headers['Authorization'] = `Bearer ${token}`

    return headers
}

/** Turns a backend `detail` (string, or a list of strings / `{msg}` items) into text. */
export function format_response_detail(detail:unknown):string | null {
    if (typeof detail === 'string') {
        const error_msg = parse_error_message(detail)
        return error_msg ? error_msg : detail
    }
    if (Array.isArray(detail)) {
        const parts = detail.map((item) => {
            if (typeof item === 'string')
                return item
            if (item && typeof item === 'object' && 'msg' in item)
                return String((item as { msg: unknown }).msg)
            return null
        }).filter((part): part is string => !!part)
        return parts.length > 0 ? parts.join('; ') : null
    }
    if (detail == null)
        return null
    return String(detail)
}

/** The user-facing message for a failed response. Never includes the URL. */
export async function response_error_message(response:Response) {
    let detail:string | null = null

    try {
        const parsed = await response.json()
        detail = format_response_detail(parsed?.detail)
    } catch (_) {
        detail = null
    }

    return detail || `HTTP error! Status — ${response.status}`
}

/** Reads a JSON body; 204, 205 and empty bodies are null. */
export async function read_json<Type>(response:Response) {
    if (response.status === 204 || response.status === 205)
        return null as Type

    const text = await response.text()

    return (text ? JSON.parse(text) : null) as Type
}

function with_prefix(error:unknown, label?:string) {
    if (!label)
        return error

    const message = error instanceof Error ? error.message : String(error)
    const cause = error instanceof Error ? error.cause : undefined

    return new Error(`${label}: ${message}`, { cause: cause })
}

async function send(url:string, options:ApiOptions) {
    const method = options.method ?? 'GET'

    console.log(`Requesting ${method}: ${url}`)

    const response = await fetch(url, {
        method: method,
        headers: api_headers(options.token, options.content_type),
        ...(options.raw_body !== undefined ?
            { body: options.raw_body } :
            options.body !== undefined && { body: JSON.stringify(options.body) }
        ),
        ...(options.signal && { signal: options.signal }),
    })

    if (!response.ok && !options.allow?.includes(response.status)) {
        console.warn(`${method} ${url} failed with status ${response.status}`)

        throw new Error(await response_error_message(response), {
            cause: response.status,
        })
    }

    return response
}

/** Sends the request and returns the Response; throws on a non-allowed error status. */
export async function api_response(url:string, options:ApiOptions = {}) {
    try {
        return await send(url, options)
    } catch (error) {
        throw with_prefix(error, options.error)
    }
}

/**
 * Sends the request and returns the parsed JSON body. 204, 205, empty bodies
 * and `allow`ed error statuses return null.
 */
export async function api_request<Type>(url:string, options:ApiOptions = {}) {
    try {
        const response = await send(url, options)

        if (!response.ok)
            return null as Type

        return await read_json<Type>(response)
    } catch (error) {
        throw with_prefix(error, options.error)
    }
}

/** Sends the request and reports whether the backend answered `expected_status`. */
export async function api_status_is(url:string, options:ApiOptions = {}, expected_status:number = 200) {
    const response = await api_response(url, options)

    return response.status === expected_status
}
