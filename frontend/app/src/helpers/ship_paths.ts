// Readable detail URLs for fittings and doctrines: `<id>-<name-slug>/`.
// The pages look the record up by the leading ID (parseInt stops at the first
// dash), so old ID-only links and links to a renamed record still resolve, and
// the page redirects them to the current URL.

const MAX_SLUG_LENGTH = 80

export function name_slug(name: string | null | undefined): string {
    const slug = (name ?? '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
    if (slug.length <= MAX_SLUG_LENGTH)
        return slug

    const cut = slug.slice(0, MAX_SLUG_LENGTH)
    const last_dash = cut.lastIndexOf('-')
    return (last_dash > 0 ? cut.slice(0, last_dash) : cut).replace(/-+$/, '')
}

// Falls back to the bare ID when a name has no ASCII letters or digits.
export function id_slug(id: number, name?: string | null): string {
    const slug = name_slug(name)
    return slug ? `${id}-${slug}` : `${id}`
}

export function fitting_path(fitting_id: number, name?: string | null): string {
    return `/ships/fittings/normal/${id_slug(fitting_id, name)}/`
}

export function fitting_render_path(fitting_id: number, name?: string | null): string {
    return `/ships/fittings/render/${id_slug(fitting_id, name)}/`
}

export function doctrine_path(doctrine_id: number, name?: string | null): string {
    return `/ships/doctrines/${id_slug(doctrine_id, name)}/`
}
