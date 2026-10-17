// Page routes known at build time, used to avoid linking to paths that 404.
const page_files = Object.keys(import.meta.glob('/src/pages/**/*.{astro,md,mdx}'))

const route_paths = page_files
    .filter(file => !file.startsWith('/src/pages/partials/') && !file.startsWith('/src/pages/api/'))
    .map(file => file
        .replace(/^\/src\/pages/, '')
        .replace(/\.(astro|md|mdx)$/, '')
        .replace(/\/index$/, '')
        || '/'
    )

const static_routes = new Set(route_paths.filter(route => !route.includes('[')))

const dynamic_routes = route_paths
    .filter(route => route.includes('['))
    .map(route => new RegExp(
        '^' + route
            .split('/')
            .map(segment => {
                if (/^\[\.\.\.[^\]]+\]$/.test(segment))
                    return '.*'
                if (/^\[[^\]]+\]$/.test(segment))
                    return '[^/]+'
                return segment.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
            })
            .join('/')
        + '$'
    ))

// Literal directories under src/pages, e.g. /alliance/corporations/application.
const static_directories = new Set(
    route_paths.flatMap(route => {
        const segments = route.split('/').filter(Boolean)
        return segments.slice(0, -1)
            .map((_, index) => `/${segments.slice(0, index + 1).join('/')}`)
            .filter(directory => !directory.includes('['))
    })
)

export function route_exists(path: string): boolean {
    const normalized = `/${path.split(/[?#]/)[0].split('/').filter(Boolean).join('/')}`

    if (static_routes.has(normalized))
        return true

    // A literal folder without its own index has no page, even when a sibling
    // dynamic route (like [corporation]) would technically match the URL.
    if (static_directories.has(normalized))
        return false

    return dynamic_routes.some(route => route.test(normalized))
}
