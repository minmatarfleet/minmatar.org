import { describe, expect, it } from 'vitest'
import { readdirSync, readFileSync } from 'fs'
import openapiTS, { astToString } from 'openapi-typescript'

import baseline from './hand_written_api_types.json'

// The API types are generated from the backend's OpenAPI document. The backend
// test app/tests/test_openapi_schema.py keeps src/types/generated/openapi.json
// current; this keeps api.d.ts generated from it. To refresh both after an
// endpoint change:
//     cd backend && UPDATE_CONTRACTS=1 python manage.py test app.tests.test_openapi_schema
//     cd frontend/app && npm run gen:api
describe('generated API types', () => {
    it('api.d.ts is generated from the committed openapi.json (npm run gen:api)', async () => {
        const schema = JSON.parse(readFileSync('src/types/generated/openapi.json', 'utf8'))
        const generated = astToString(await openapiTS(schema, { defaultNonNullable: false }))
        const committed = readFileSync('src/types/generated/api.d.ts', 'utf8')

        expect(committed.slice(committed.indexOf('export '))).toBe(generated)
    }, 30_000)

    it('no new hand-written API interfaces: alias the generated schema instead', () => {
        const files = [
            'src/types/api.minmatar.org.ts',
            ...readdirSync('src/helpers/api.minmatar.org').filter(f => f.endsWith('.ts')).map(f => `src/helpers/api.minmatar.org/${f}`),
        ]
        const allowed:Record<string, Record<string, string>> = baseline.files
        const added:string[] = []
        const gone:string[] = []

        for (const file of files) {
            const names = [...readFileSync(file, 'utf8').matchAll(/^export interface (\w+)/gm)].map(match => match[1])
            const known = allowed[file] ?? {}
            for (const name of names) if (!(name in known)) added.push(`${file}: ${name}`)
            for (const name of Object.keys(known)) if (!names.includes(name)) gone.push(`${file}: ${name}`)
        }
        for (const file of Object.keys(allowed)) if (!files.includes(file)) gone.push(file)

        // A new API type: `export type Thing = ApiResponse<'ThingResponse'>` (src/types/api.minmatar.org.ts).
        expect(added, 'hand-written API interfaces; alias the generated schema').toEqual([])
        // Aliased or deleted: drop the name from testing/types/hand_written_api_types.json.
        expect(gone, 'stale entries in hand_written_api_types.json').toEqual([])
    })
})
