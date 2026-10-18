import { i18n } from '@helpers/i18n'

export const HTTP_404_Not_Found = (body:BodyInit | null = null):Response => {
    return new Response(body, {
        status: 404,
        statusText: 'Not found'
    });
}

export const HTTP_403_Forbidden = () => {
    return new Response(
        `<!doctype html>
            <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <title>403 Unauthorized</title>
                    <meta name="description" content="Docking request denied!">
                    <link rel="icon" type="image/svg+xml" href="/images/fleet-logo.png">

                    <style>
                        body {
                            background-color: #121212;
                        }
                    </style>
                    
                    <script>
                        async function fetchAndReplace(url) {
                            try {
                                // Fetch the new page content
                                const response = await fetch(url);
                    
                                if (!response.ok) {
                                    throw new Error(\`Error fetching the page: \${response.status} \${response.statusText}\`);
                                }
                    
                                // Get the response as text
                                const newHTML = await response.text();
                    
                                // Replace the entire page's HTML
                                document.open(); // Clear the current document
                                document.write(newHTML); // Write the new content
                                document.close(); // Close the document to finalize changes
                            } catch (error) {
                                console.error("Error replacing page content:", error);
                            }
                        }
                    
                        fetchAndReplace("/403");
                    </script>
                </head>
                <body></body>
            </html>`, {
            status: 403,
            headers: { 'Content-type': 'text/html' },
            statusText: 'Forbidden',
        }
    ) as Response;
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

/** Send a visitor without a session to the login notice, then back here. */
export const login_redirect = (context: { request: Request, url: URL }): Response => {
    const { translatePath } = i18n(context.url)
    const auth_init = translatePath('/redirects/auth_init')
    const return_to = encodeURIComponent(login_return_url(context.request))

    return partial_redirect(context.request, `${auth_init}?redirect_url=${return_to}`)
}
