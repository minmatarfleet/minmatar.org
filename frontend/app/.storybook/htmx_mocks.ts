// Stories run without the Astro server, so htmx requests (LazyPartial,
// ErrorRefetch, HtmxPager, hx-post buttons) are answered here instead.
//
//   parameters: {
//       htmx: {
//           '/partials/fleets_component': '<p>Fleet list</p>',
//           '/partials/slow': { body: '<p>Late</p>', delay: 1500 },
//           '/partials/broken': { status: 500, body: '' },
//           '/partials/echo': (url) => `<p>${url.searchParams.get('page')}</p>`,
//       },
//   }
//
// Keys match the request path (query string ignored) or are a RegExp
// source when wrapped in slashes ('/^\\/partials\\/fleet_\\d+/').
// Unmocked htmx requests get an empty 404, so a story never reaches the site.

export type HtmxMockResponse = string | {
    body?:      string;
    status?:    number;
    delay?:     number;
    headers?:   Record<string, string>;
}

export type HtmxMock = HtmxMockResponse | ((url: URL, body: string | null) => HtmxMockResponse)

export type HtmxMocks = Record<string, HtmxMock>

declare global {
    interface Window {
        __rust_htmx_mocks?: HtmxMocks;
        __rust_htmx_requests?: { method: string; url: string; body: string | null }[];
    }
}

function find_mock(mocks: HtmxMocks, url: URL): HtmxMock | undefined {
    if (url.pathname in mocks)
        return mocks[url.pathname]

    const trimmed = url.pathname.replace(/\/$/, '')
    for (const [key, mock] of Object.entries(mocks)) {
        if (key.replace(/\/$/, '') === trimmed)
            return mock
        if (key.length > 2 && key.startsWith('/^') && key.endsWith('/') && new RegExp(key.slice(1, -1)).test(url.pathname))
            return mock
    }
    return undefined
}

function define(xhr: XMLHttpRequest, key: string, value: unknown) {
    Object.defineProperty(xhr, key, { configurable: true, get: () => value })
}

const pending = new Set<number>()

// A story change cancels in-flight mocked requests, as a page navigation
// would; a late answer would swap into markup that is already gone.
export function cancel_pending_htmx_mocks(win: Window) {
    for (const timer of pending)
        win.clearTimeout(timer)
    pending.clear()
}

export function install_htmx_mocks(win: Window) {
    const proto = win.XMLHttpRequest.prototype as any
    if (proto.__rust_mocked)
        return
    proto.__rust_mocked = true

    const original_open = proto.open
    const original_send = proto.send
    const original_set_header = proto.setRequestHeader

    proto.open = function (method: string, url: string, ...rest: unknown[]) {
        this.__rust_method = method
        this.__rust_url = new URL(url, win.location.href)
        this.__rust_headers = {}
        return original_open.call(this, method, url, ...rest)
    }

    proto.setRequestHeader = function (name: string, value: string) {
        this.__rust_headers[name.toLowerCase()] = value
        return original_set_header.call(this, name, value)
    }

    proto.send = function (body: string | null = null) {
        const url: URL = this.__rust_url
        const is_htmx = this.__rust_headers?.['hx-request'] === 'true'
        if (!url || !is_htmx)
            return original_send.call(this, body)

        win.__rust_htmx_requests = win.__rust_htmx_requests ?? []
        win.__rust_htmx_requests.push({ method: this.__rust_method, url: url.pathname + url.search, body })

        const mock = find_mock(win.__rust_htmx_mocks ?? {}, url)
        const resolved = typeof mock === 'function' ? mock(url, body) : mock
        const response = typeof resolved === 'string'
            ? { body: resolved, status: 200 }
            : (resolved ?? { body: '', status: 404 })

        const status = response.status ?? 200
        const headers = response.headers ?? {}
        const text = response.body ?? ''

        const timer = win.setTimeout(() => {
            pending.delete(timer)
            define(this, 'readyState', 4)
            define(this, 'status', status)
            define(this, 'statusText', status < 400 ? 'OK' : 'Error')
            define(this, 'responseText', text)
            define(this, 'response', text)
            define(this, 'responseURL', url.href)
            this.getResponseHeader = (name: string) => headers[name] ?? headers[name.toLowerCase()] ?? null
            this.getAllResponseHeaders = () => Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join('\r\n')
            // dispatchEvent also runs the on* handler properties htmx sets.
            for (const type of ['loadstart', 'readystatechange', 'load', 'loadend'])
                this.dispatchEvent(type === 'readystatechange' ? new Event(type) : new ProgressEvent(type))
        }, response.delay ?? 120)
        pending.add(timer)
    }
}
