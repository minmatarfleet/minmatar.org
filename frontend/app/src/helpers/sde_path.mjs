/**
 * Where the local SDE snapshot lives: the one config point for the site
 * (helpers/sde_db.ts), drizzle-kit (sde.drizzle.config.ts) and the report
 * extractors (scripts/*_extract.mjs).
 *
 * The snapshot is a Fuzzwork-format SQLite conversion of CCP's static data
 * export, named by CCP build number: src/data/sde-<build>.sqlite. It is not in
 * git (about 550 MB). See docs/frontend-sde.md to provision or upgrade it.
 *
 * Plain JavaScript so the Node extractor scripts can import it too.
 */
import { existsSync, statSync } from 'node:fs'
import { join } from 'node:path'

/** The SDE build the site expects. Bump it together with the file on every host. */
export const SDE_BUILD = 3409592

/**
 * Older builds still accepted (with a warning) while hosts are upgraded.
 * Empty this once every host has sde-<SDE_BUILD>.sqlite.
 */
export const SDE_FALLBACK_BUILDS = [3316380]

/** File name for a build, e.g. sde-3409592.sqlite. */
export const sde_file_name = (build) => `sde-${build}.sqlite`

const usable = (path) => {
    try {
        return existsSync(path) && statSync(path).size > 0
    } catch {
        return false
    }
}

/**
 * Resolve the SDE file. `SDE_PATH` overrides everything. Otherwise the pinned
 * build is used, then a fallback build with a warning. Throws a clear error
 * when nothing usable is found (instead of opening an empty database).
 *
 * @param {{ root?: string, env?: Record<string, string | undefined>, warn?: (message: string) => void }} [options]
 * @returns {{ path: string, build: number | null, fallback: boolean }}
 */
export function resolve_sde_path({ root = '.', env = process.env, warn = console.warn } = {}) {
    if (env.SDE_PATH) {
        if (!usable(env.SDE_PATH))
            throw new Error(`SDE_PATH is set to ${env.SDE_PATH}, but that file is missing or empty. See docs/frontend-sde.md.`)
        return { path: env.SDE_PATH, build: null, fallback: false }
    }

    const pinned = join(root, 'src', 'data', sde_file_name(SDE_BUILD))
    if (usable(pinned))
        return { path: pinned, build: SDE_BUILD, fallback: false }

    for (const build of SDE_FALLBACK_BUILDS) {
        const path = join(root, 'src', 'data', sde_file_name(build))
        if (usable(path)) {
            warn(`SDE build ${SDE_BUILD} not found at ${pinned}; using older build ${build} (${path}). See docs/frontend-sde.md.`)
            return { path, build, fallback: true }
        }
    }

    throw new Error(
        `SDE snapshot missing: expected ${pinned} (CCP build ${SDE_BUILD}). `
        + 'Download it as described in docs/frontend-sde.md, or set SDE_PATH.',
    )
}
