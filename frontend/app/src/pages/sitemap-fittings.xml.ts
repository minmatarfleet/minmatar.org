import type { APIRoute } from 'astro'

import { get_fittings } from '@helpers/api.minmatar.org/ships'

export const prerender = false

function escape_xml(s: string) {
    return s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
}

export const GET: APIRoute = async ({ request }) => {
    const origin = new URL(request.url).origin

    try {
        const fittings = await get_fittings()
        const entries = fittings.map((f) => {
            const loc = `${origin}/ships/fittings/normal/${f.id}`
            const lastmod = f.updated_at
                ? new Date(f.updated_at as unknown as string).toISOString().slice(0, 10)
                : ''
            return { loc, lastmod }
        })

        const url_blocks = entries
            .map(({ loc, lastmod }) => {
                const lastmod_xml = lastmod ? `\n    <lastmod>${lastmod}</lastmod>` : ''
                return `  <url>\n    <loc>${escape_xml(loc)}</loc>${lastmod_xml}\n  </url>`
            })
            .join('\n')

        const body = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${url_blocks}
</urlset>`

        return new Response(body, {
            headers: {
                'Content-Type': 'application/xml; charset=utf-8',
            },
        })
    } catch {
        const empty = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>`
        return new Response(empty, {
            headers: {
                'Content-Type': 'application/xml; charset=utf-8',
            },
        })
    }
}
