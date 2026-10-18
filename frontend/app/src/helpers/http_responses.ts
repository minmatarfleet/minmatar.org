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

/** The login notice, which returns to `return_url` (query string included) afterwards. */
export const login_url = (context: { url: URL }, return_url: string = context.url.href): string => {
    const { translatePath } = i18n(context.url)
    return `${translatePath('/redirects/auth_init')}?redirect_url=${encodeURIComponent(return_url)}`
}

/**
 * Send a visitor without a session to the login notice, then back to this
 * URL. Every page and partial that needs a login returns this.
 */
export const login_redirect = (context: { request: Request, url: URL }): Response => {
    return new Response(null, {
        status: 302,
        headers: { Location: login_url(context, context.request.url) },
    })
}
