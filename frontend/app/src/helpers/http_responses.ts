import { i18n } from '@helpers/i18n'

export const HTTP_404_Not_Found = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

/** Marks a bare status response that middleware swaps for the matching status page. */
export const STATUS_PAGE_HEADER = 'X-Status-Page'

/**
 * 403 for pages and partials. Middleware renders the /403 page in its place
 * (keeping the 403 status) for page requests; htmx partials and /api routes
 * get the bare status.
 */
export const HTTP_403_Forbidden = ():Response => {
    return new Response(null, {
        status: 403,
        statusText: 'Forbidden',
        headers: { [STATUS_PAGE_HEADER]: '403' },
    });
}

/** The status page to render in place of `response`, or null to send it as is. */
export const status_page_rewrite = (request:Request, response:Response):string | null => {
    const status_page = response.headers.get(STATUS_PAGE_HEADER)
    if (!status_page || String(response.status) !== status_page)
        return null

    if (request.headers.get('HX-Request'))
        return null

    const pathname = new URL(request.url).pathname
    if (pathname.startsWith('/partials/') || pathname.startsWith('/api/'))
        return null

    return `/${status_page}`
}

export const HTTP_200_Success = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 200,
        statusText: 'Success'
    });
}

export const HTTP_400_Bad_Request = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 400,
        statusText: 'Bad Request'
    });
}

export const HTTP_500_Server_Error = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 500,
        statusText: 'Server Error'
    });
}

export const HTTP_502_Server_Error = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 502,
        statusText: 'Service Unavailable'
    });
}

/** htmx marks every request it sends with `HX-Request: true`. */
export const is_htmx_request = (request: Request): boolean => {
    return request.headers.get('HX-Request') === 'true'
}

/**
 * Redirect from a partial. htmx follows a 302 inside its XHR and swaps the
 * target page into the fragment, so answer an htmx request with 200 and
 * `HX-Redirect`, which makes htmx navigate the whole window. Any other
 * request (someone opening the partial URL directly) gets a normal 302.
 */
export const partial_redirect = (request: Request, location: string): Response => {
    if (is_htmx_request(request)) {
        return new Response('', {
            status: 200,
            headers: {
                'Content-Type': 'text/html',
                'HX-Redirect': location,
            },
        })
    }

    return new Response(null, {
        status: 302,
        headers: { Location: location },
    })
}

/**
 * The URL to come back to after logging in. For an htmx request that is the
 * page the user is on (htmx sends it as `HX-Current-URL`; fall back to
 * `Referer`), not the partial URL, which renders as an unstyled fragment.
 */
export const login_return_url = (request: Request): string => {
    if (!is_htmx_request(request))
        return request.url

    return request.headers.get('HX-Current-URL')
        || request.headers.get('Referer')
        || request.url
}

/** The login notice, which returns to `return_url` (query string included) afterwards. */
export const login_url = (context: { url: URL }, return_url: string = context.url.href): string => {
    const { translatePath } = i18n(context.url)
    return `${translatePath('/redirects/auth_init')}?redirect_url=${encodeURIComponent(return_url)}`
}

/**
 * Send a visitor without a session to the login notice, then back here.
 * Every page and partial that needs a login returns this; htmx requests get
 * `HX-Redirect` so the whole window navigates.
 */
export const login_redirect = (context: { request: Request, url: URL }): Response => {
    return partial_redirect(context.request, login_url(context, login_return_url(context.request)))
}
