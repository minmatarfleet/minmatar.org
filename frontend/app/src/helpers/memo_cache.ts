/**
 * A small per-process cache for backend reads that many requests repeat.
 *
 * - Values live for `ttl_ms`; a TTL of 0 (or less) never caches.
 * - Concurrent misses for one key share a single in-flight promise, so a page
 *   and the partials it loads at the same time make one backend call.
 * - Failures are never cached: the rejection reaches every waiting caller and
 *   the next call tries again.
 * - At `max_entries` the least recently used key is dropped.
 *
 * The frontend runs as one Node process (adapter: node standalone), so this
 * is shared by every request that process serves.
 */

interface Entry<T> {
    value:      T;
    expires:    number;
}

export interface MemoCache<T> {
    get(key: string, ttl_ms: number, load: () => Promise<T>): Promise<T>;
    clear(): void;
    readonly size: number;
}

export function create_memo_cache<T>(max_entries: number = 5000, now: () => number = () => Date.now()): MemoCache<T> {
    const entries = new Map<string, Entry<T>>()
    const in_flight = new Map<string, Promise<T>>()

    return {
        get(key, ttl_ms, load) {
            if (!(ttl_ms > 0))
                return load()

            const hit = entries.get(key)
            if (hit && hit.expires > now()) {
                // Re-insert to mark it most recently used.
                entries.delete(key)
                entries.set(key, hit)
                return Promise.resolve(hit.value)
            }
            if (hit)
                entries.delete(key)

            const pending = in_flight.get(key)
            if (pending)
                return pending

            const promise = load().then(
                (value) => {
                    in_flight.delete(key)
                    entries.set(key, { value, expires: now() + ttl_ms })
                    while (entries.size > max_entries)
                        entries.delete(entries.keys().next().value as string)
                    return value
                },
                (error) => {
                    in_flight.delete(key)
                    throw error
                },
            )
            in_flight.set(key, promise)
            return promise
        },
        clear() {
            entries.clear()
            in_flight.clear()
        },
        get size() {
            return entries.size
        },
    }
}

/**
 * A TTL in ms from an env var in seconds. Unset uses `default_seconds`; tests
 * (VITEST) default to 0 so cached values never leak from one test to the next.
 */
export function ttl_ms_from_env(name: string, default_seconds: number): number {
    const raw = process.env[name]
    if (raw !== undefined && raw !== '') {
        const seconds = Number(raw)
        return Number.isFinite(seconds) && seconds > 0 ? seconds * 1000 : 0
    }
    if (process.env.VITEST)
        return 0
    return default_seconds * 1000
}
