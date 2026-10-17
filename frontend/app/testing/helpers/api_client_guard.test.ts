import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

const API_DIR = path.resolve(__dirname, '../../src/helpers/api.minmatar.org')

// Every backend call goes through client.ts so headers, errors and the
// cause=status contract live in one place.
const FORBIDDEN = [
    /\bfetch\(/,
    /\bget_error_message\b/,
    /\bparse_response_error\b/,
    /['"]Authorization['"]/,
    /function (auth_headers|build_headers|request_json|request)\b/,
]

describe('helpers/api.minmatar.org', () => {
    const files = fs.readdirSync(API_DIR).filter((f) => f.endsWith('.ts') && f !== 'client.ts')

    it.each(files)('%s calls the backend only through client.ts', (file) => {
        const source = fs.readFileSync(path.join(API_DIR, file), 'utf8')
        const hits = FORBIDDEN.filter((pattern) => pattern.test(source)).map(String)

        expect(hits).toEqual([])
    })
})
