/**
 * Loaders start independent backend calls together with Promise.allSettled,
 * then read the results in the order the page used to await them. A failure
 * surfaces exactly where it used to, and the values before it are kept.
 */
export function settled_value<T>(result: PromiseSettledResult<T>): T {
    if (result.status === 'rejected')
        throw result.reason

    return result.value
}
