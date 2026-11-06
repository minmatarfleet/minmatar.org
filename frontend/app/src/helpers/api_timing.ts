/**
 * Per-request record of the backend calls a page makes, for measuring how
 * long a navigation waits on the API.
 *
 * Off unless `API_TIMING_LOG=1`: the middleware then runs each request inside
 * a store, `api_request`/`api_response` add one entry per call, and one log
 * line is written when the response body has finished streaming (the layout's
 * calls run after the headers are sent, so a response header would miss them).
 */
import { AsyncLocalStorage } from 'node:async_hooks'

export interface ApiTimingEntry {
    endpoint:   string;
    start:      number;
    end:        number;
    status:     number | null;
}

export interface ApiTimingStore {
    started:    number;
    entries:    ApiTimingEntry[];
}

const storage = new AsyncLocalStorage<ApiTimingStore>()

export function api_timing_enabled():boolean {
    return process.env.API_TIMING_LOG === '1'
}

export function new_api_timing_store():ApiTimingStore {
    return { started: performance.now(), entries: [] }
}

export function run_with_api_timing<T>(store:ApiTimingStore, fn:() => T):T {
    return storage.run(store, fn)
}

/** `/api/fleets/92221/members?x=1` → `/api/fleets/:id/members`. */
export function timing_endpoint(url:string):string {
    let path = url
    try {
        path = new URL(url).pathname
    } catch (_) {
        path = url.split('?')[0]
    }
    return path.replace(/\/\d+(?=\/|$)/g, '/:id')
}

/** Starts timing one call; the returned function records it. A no-op outside a store. */
export function start_api_timing(url:string):(status:number | null) => void {
    const store = storage.getStore()
    if (!store)
        return () => {}

    const start = performance.now()
    return (status) => {
        store.entries.push({ endpoint: timing_endpoint(url), start, end: performance.now(), status })
    }
}

/** How many sequential waits the calls form: calls that overlap count as one round. */
export function count_rounds(entries:ApiTimingEntry[]):number {
    const sorted = [...entries].sort((a, b) => a.start - b.start)
    let rounds = 0
    let round_end = -Infinity
    for (const entry of sorted) {
        if (entry.start >= round_end) {
            rounds++
            round_end = entry.end
        } else {
            round_end = Math.max(round_end, entry.end)
        }
    }
    return rounds
}

export function format_api_timing(method:string, path:string, store:ApiTimingStore, now:number = performance.now()):string {
    const entries = [...store.entries].sort((a, b) => a.start - b.start)
    const api_ms = entries.reduce((total, entry) => total + (entry.end - entry.start), 0)
    const calls = entries
        .map((entry) => `${entry.endpoint}(${Math.round(entry.end - entry.start)}ms${entry.status && entry.status >= 400 ? ` ${entry.status}` : ''})`)
        .join(' ')

    return `[api-timing] ${method} ${path} calls=${entries.length} rounds=${count_rounds(entries)} api_ms=${Math.round(api_ms)} render_ms=${Math.round(now - store.started)} :: ${calls}`
}

/** Logs the store once the body has finished streaming. */
export function log_api_timing_on_finish(response:Response, method:string, path:string, store:ApiTimingStore):Response {
    const log = () => console.log(format_api_timing(method, path, store))

    if (!response.body) {
        log()
        return response
    }

    const body = response.body.pipeThrough(new TransformStream({
        flush() {
            log()
        },
    }))

    return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
    })
}
