// Show which SDE snapshot the site will open and whether it looks right.
//   npm run sde:check
import { createHash } from 'node:crypto'
import { createReadStream, statSync } from 'node:fs'
import path from 'node:path'
import Database from 'better-sqlite3'
import { SDE_BUILD, resolve_sde_path } from '../src/helpers/sde_path.mjs'

const ROOT = path.resolve(import.meta.dirname, '..')
const { path: sde_path, build, fallback } = resolve_sde_path({ root: ROOT })

const sha256 = await new Promise((resolve, reject) => {
    const hash = createHash('sha256')
    createReadStream(sde_path).on('data', chunk => hash.update(chunk)).on('end', () => resolve(hash.digest('hex'))).on('error', reject)
})

const db = new Database(sde_path, { readonly: true, fileMustExist: true })
const count = (table) => db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get().n
const newest = db.prepare('SELECT typeID, typeName FROM invTypes ORDER BY typeID DESC LIMIT 1').get()
const types = count('invTypes')
const systems = count('mapSolarSystems')
db.close()

console.log(`file:      ${path.relative(ROOT, sde_path)}${fallback ? ` (fallback; expected build ${SDE_BUILD})` : ''}`)
console.log(`build:     ${build ?? 'SDE_PATH override'}`)
console.log(`size:      ${(statSync(sde_path).size / 1024 / 1024).toFixed(0)} MB`)
console.log(`sha256:    ${sha256}`)
console.log(`types:     ${types} (newest ${newest.typeID} ${newest.typeName})`)
console.log(`systems:   ${systems}`)
