import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import { SDE_BUILD, SDE_FALLBACK_BUILDS, resolve_sde_path, sde_file_name } from '@helpers/sde_path.mjs'

let root = ''
const data = (name: string, bytes = 'x') => {
    mkdirSync(join(root, 'src', 'data'), { recursive: true })
    writeFileSync(join(root, 'src', 'data', name), bytes)
}

beforeEach(() => { root = mkdtempSync(join(tmpdir(), 'sde-path-')) })
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

describe('resolve_sde_path', () => {
    it('uses the pinned build when present', () => {
        data(sde_file_name(SDE_BUILD))
        data(sde_file_name(SDE_FALLBACK_BUILDS[0]))
        expect(resolve_sde_path({ root, env: {} })).toEqual({
            path: join(root, 'src', 'data', `sde-${SDE_BUILD}.sqlite`),
            build: SDE_BUILD,
            fallback: false,
        })
    })

    it('falls back to an older build with a warning', () => {
        data(sde_file_name(SDE_FALLBACK_BUILDS[0]))
        const warnings: string[] = []
        const resolved = resolve_sde_path({ root, env: {}, warn: message => warnings.push(message) })
        expect(resolved.build).toBe(SDE_FALLBACK_BUILDS[0])
        expect(resolved.fallback).toBe(true)
        expect(warnings[0]).toContain(`SDE build ${SDE_BUILD} not found`)
    })

    it('treats an empty file as missing and throws a clear error', () => {
        data(sde_file_name(SDE_BUILD), '')
        expect(() => resolve_sde_path({ root, env: {}, warn: () => {} })).toThrow(/SDE snapshot missing: expected .*sde-\d+\.sqlite .*docs\/frontend-sde\.md/)
        // It must not create a database file as a side effect.
        expect(existsSync(join(root, 'src', 'data', sde_file_name(SDE_FALLBACK_BUILDS[0])))).toBe(false)
    })

    it('honours SDE_PATH and rejects a missing override', () => {
        data('custom.sqlite')
        const custom = join(root, 'src', 'data', 'custom.sqlite')
        expect(resolve_sde_path({ root, env: { SDE_PATH: custom } })).toEqual({ path: custom, build: null, fallback: false })
        expect(() => resolve_sde_path({ root, env: { SDE_PATH: join(root, 'nope.sqlite') } })).toThrow(/SDE_PATH is set/)
    })
})

describe('sde_db', () => {
    it('does not open (or create) the database on import', async () => {
        const previous = process.env.SDE_PATH
        process.env.SDE_PATH = join(root, 'missing.sqlite')
        try {
            const module = await import('@helpers/sde_db')
            expect(module.sde_db).toBeTruthy()
            expect(existsSync(join(root, 'missing.sqlite'))).toBe(false)
        } finally {
            if (previous === undefined) delete process.env.SDE_PATH
            else process.env.SDE_PATH = previous
        }
    })
})

describe('SDE queries through the lazy handle', () => {
    const has_local_sde = (() => {
        try { resolve_sde_path({ warn: () => {} }); return true } catch { return false }
    })()

    it.runIf(has_local_sde)('resolve type names from the local snapshot', async () => {
        const { get_type_names } = await import('@helpers/sde/items')
        const names = await get_type_names([587, 0])
        expect(names.get(587)).toBe('Rifter')
    })
})
