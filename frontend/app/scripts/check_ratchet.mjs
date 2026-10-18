#!/usr/bin/env node
// Type-check ratchet around `astro check`.
//
// The project carries a backlog of type errors, so a plain `astro check` can
// never pass. This runs it, counts errors per file and compares them with
// testing/conventions/type_check_baseline.json: the check fails only when a
// file has more errors than its baseline (new files are allowed zero).
//
//   npm run check             fail on new errors
//   npm run check:baseline    rewrite the baseline from the current errors
//
// Fixing errors never fails the check; run check:baseline to lock the gain in.

import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const APP_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..')
const BASELINE_PATH = join(APP_ROOT, 'testing/conventions/type_check_baseline.json')
const update = process.argv.includes('--update')

const astro = join(APP_ROOT, 'node_modules/.bin/astro')
const run = spawnSync(astro, ['check', '--minimumSeverity', 'error'], {
    cwd: APP_ROOT,
    encoding: 'utf8',
    maxBuffer: 256 * 1024 * 1024,
    env: { ...process.env, FORCE_COLOR: '0', NO_COLOR: '1' },
})
const output = `${run.stdout ?? ''}\n${run.stderr ?? ''}`.replace(/\x1b\[[0-9;]*m/g, '')

const result = output.match(/Result \((\d+) files?\)/)
if (!result) {
    process.stdout.write(output)
    console.error('\ncheck_ratchet: astro check did not finish (no "Result (N files)" line).')
    process.exit(2)
}
const checked_files = Number(result[1])
// Guard against the original failure mode: a tsconfig that resolves no inputs
// makes astro check report "0 files" and pass while checking nothing.
if (checked_files === 0) {
    console.error('check_ratchet: astro check type-checked 0 files; the tsconfig resolves no inputs.')
    process.exit(2)
}

const errors = new Map()
const diagnostics = new Map()
for (const m of output.matchAll(/^(\S[^\n]*?):(\d+):(\d+) - error ([^\n]*)$/gm)) {
    const [, file, line, column, message] = m
    errors.set(file, (errors.get(file) ?? 0) + 1)
    if (!diagnostics.has(file)) diagnostics.set(file, [])
    diagnostics.get(file).push(`    ${file}:${line}:${column} ${message}`)
}
const total = [...errors.values()].reduce((a, b) => a + b, 0)
const reported = Number(output.match(/- (\d+) errors?/)?.[1] ?? 0)
if (reported !== total) {
    process.stdout.write(output)
    console.error(`\ncheck_ratchet: parsed ${total} errors but astro check reported ${reported}; the output format changed.`)
    process.exit(2)
}

if (update) {
    const sorted = Object.fromEntries([...errors].sort(([a], [b]) => a.localeCompare(b)))
    writeFileSync(BASELINE_PATH, JSON.stringify(sorted, null, 4) + '\n')
    console.log(`check_ratchet: wrote ${Object.keys(sorted).length} files / ${total} errors to ${BASELINE_PATH}`)
    process.exit(0)
}

const baseline = existsSync(BASELINE_PATH) ? JSON.parse(readFileSync(BASELINE_PATH, 'utf8')) : {}
const over = []
const improved = []
for (const [file, count] of errors) {
    const allowed = baseline[file] ?? 0
    if (count > allowed) over.push({ file, count, allowed })
}
for (const [file, allowed] of Object.entries(baseline)) {
    const count = errors.get(file) ?? 0
    if (count < allowed) improved.push({ file, count, allowed })
}

const baseline_total = Object.values(baseline).reduce((a, b) => a + b, 0)
console.log(`check_ratchet: ${checked_files} files checked, ${total} errors (baseline ${baseline_total}).`)
if (improved.length) {
    console.log(`check_ratchet: ${improved.length} file(s) are below their baseline; run \`npm run check:baseline\` to lock that in.`)
}
if (over.length) {
    console.error('\ncheck_ratchet: new type errors (fix them; the baseline only shrinks):')
    for (const { file, count, allowed } of over) {
        console.error(`  ${file}: ${count} errors (baseline ${allowed})`)
        console.error(diagnostics.get(file).join('\n'))
    }
    process.exit(1)
}
