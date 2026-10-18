/**
 * The one way the server calls ESI directly. Sends an identifying
 * User-Agent and the same X-Compatibility-Date as the backend
 * (backend/eveonline/client.py ESI_COMPATIBILITY_DATE), and throws errors
 * whose `cause` is the HTTP status.
 */
export const ESI_URL = import.meta.env.EVE_API_URL ?? 'https://esi.evetech.net/latest'
export const ESI_COMPATIBILITY_DATE = '2026-06-09'
export const ESI_USER_AGENT = 'MinmatarFleetWeb (+https://github.com/minmatarfleet/minmatar.org)'

export interface EsiOptions {
    method?:        string;
    body?:          unknown;
    /** Error message prefix, e.g. `Error fetching alliance`. */
    error:          string;
    /** Statuses that return `fallback` instead of throwing. */
    allow?:         number[];
    fallback?:      unknown;
    /** Keep successful GET responses in memory for this long. */
    cache_ms?:      number;
}

const MAX_CACHE_ENTRIES = 5000
const cache = new Map<string, { expires: number, value: unknown }>()

export function esi_headers() {
    return {
        'Content-Type': 'application/json',
        'User-Agent': ESI_USER_AGENT,
        'X-Compatibility-Date': ESI_COMPATIBILITY_DATE,
    }
}

export function clear_esi_cache() {
    cache.clear()
}

export async function esi_request<Type>(path:string, options:EsiOptions):Promise<Type> {
    const url = `${ESI_URL}${path}`
    const method = options.method ?? 'GET'
    const cache_key = options.cache_ms && method === 'GET' ? url : null

    if (cache_key) {
        const hit = cache.get(cache_key)
        if (hit && hit.expires > Date.now())
            return hit.value as Type
        cache.delete(cache_key)
    }

    console.log(`Requesting ${method}: ${url}`)

    try {
        const response = await fetch(url, {
            method: method,
            headers: esi_headers(),
            ...(options.body !== undefined && { body: JSON.stringify(options.body) }),
        })

        if (!response.ok) {
            if (options.allow?.includes(response.status))
                return options.fallback as Type

            throw new Error(`HTTP error! Status: ${response.status}`, { cause: response.status })
        }

        const value = await response.json() as Type

        if (cache_key) {
            if (cache.size >= MAX_CACHE_ENTRIES)
                cache.delete(cache.keys().next().value as string)
            cache.set(cache_key, { expires: Date.now() + (options.cache_ms as number), value: value })
        }

        return value
    } catch (error) {
        throw new Error(`${options.error}: ${error.message}`, { cause: error.cause })
    }
}
