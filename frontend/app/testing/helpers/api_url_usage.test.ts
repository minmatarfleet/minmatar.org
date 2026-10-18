import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const SRC = path.resolve(__dirname, '../../src')
const ALLOWED = [
    path.join(SRC, 'helpers', 'env.ts'),
    path.join(SRC, 'helpers', 'api.minmatar.org') + path.sep,
]

function source_files(dir: string): string[] {
    return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) return source_files(full)
        return /\.(ts|astro|js)$/.test(entry.name) ? [full] : []
    })
}

describe('backend base URLs', () => {
    // API_URL is the server-to-backend address (http://app:8000 in docker).
    // Anything the browser follows must use get_public_api_url(); server-side
    // fetches outside the API helpers use get_internal_api_url().
    it('reads import.meta.env.API_URL only in env.ts and the API helpers', () => {
        const offenders = source_files(SRC)
            .filter((file) => !ALLOWED.some((allowed) => file === allowed || file.startsWith(allowed)))
            .filter((file) => fs.readFileSync(file, 'utf8')
                .split('\n')
                .some((line) => line.includes('import.meta.env.API_URL') && !line.trim().startsWith('//')))
            .map((file) => path.relative(SRC, file))

        expect(offenders).toEqual([])
    })
})
