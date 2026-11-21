// Browser stand-in for node:async_hooks. Some components import server
// helpers (request timing in src/helpers/api_timing.ts) whose module graph
// reaches the preview bundle; the render server uses the real module.
export class AsyncLocalStorage<T> {
    private store: T | undefined
    getStore() { return this.store }
    run<R>(store: T, callback: (...args: unknown[]) => R, ...args: unknown[]): R {
        const previous = this.store
        this.store = store
        try { return callback(...args) } finally { this.store = previous }
    }
    enterWith(store: T) { this.store = store }
    disable() { this.store = undefined }
}
export default { AsyncLocalStorage }
