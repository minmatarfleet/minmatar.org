// Browser stand-in for src/helpers/sde_db.ts in the preview bundle. The
// preview follows .astro frontmatter imports, and bundling better-sqlite3 and
// drizzle for the browser fails at import time. Queries only ever run on the
// render server, which loads the real module.
const unavailable = () => {
    throw new Error('The SDE database is only available on the render server')
}

export function open_sde_db(): never {
    return unavailable()
}

export const sde_db = new Proxy({}, { get: unavailable }) as never
