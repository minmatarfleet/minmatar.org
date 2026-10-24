import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('@helpers/api.minmatar.org/gates', () => ({
    get_user_gates: vi.fn(),
}))

import { get_user_gates } from '@helpers/api.minmatar.org/gates'
import {
    ANONYMOUS_GATES,
    GATES,
    can,
    can_custom,
    gate_context_from,
    get_gates,
    reset_gate_mismatch_reporter,
    set_gate_mismatch_reporter,
    type GateContext,
    type GateKey,
    type GateMismatch,
} from '@helpers/gates'
import sitemap from '@json/sitemap.json'

const SRC = join(__dirname, '../../src')

function context(overrides: Partial<GateContext> = {}): GateContext {
    return {
        ...ANONYMOUS_GATES,
        user_id: 7,
        reported: new Set(),
        ...overrides,
    }
}

function token(payload: Record<string, unknown>) {
    const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url')
    return `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(payload)}.signature`
}

function astro(cookie?: string) {
    return {
        cookies: {
            has: (name: string) => name === 'auth_token' && cookie !== undefined,
            get: (name: string) => (name === 'auth_token' && cookie !== undefined ? { value: cookie } : undefined),
        },
        locals: {} as Record<string, any>,
    }
}

function source_files(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
        const path = join(dir, name)
        if (statSync(path).isDirectory()) return source_files(path)
        return /\.(astro|ts)$/.test(name) ? [path] : []
    })
}

/**
 * The inline checks this replaced, copied from the call sites. Legacy mode
 * must give the same answer for every superuser / permission combination.
 */
type Inline = (is_superuser: boolean, user_permissions: string[]) => boolean
const INLINE: Partial<Record<GateKey, Inline>> = {
    'fleets.view': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('fleets.view_evefleet'),
    'fleets.create': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('fleets.add_evefleet'),
    'fleets.delete': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('fleets.delete_evefleet'),
    'fleets.manage_any': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('fleets.manage_any_fleet'),
    'campaigns.view': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('campaigns.view_campaign'),
    'campaigns.manage': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('campaigns.change_campaign'),
    'posts.create': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('posts.add_evepost'),
    'srp.view': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('srp.view_evefleetshipreimbursement'),
    'srp.resolve': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('srp.add_evefleetshipreimbursement'),
    'srp.process': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('srp.change_evefleetshipreimbursement'),
    'srp.process#strict': (_is_superuser, user_permissions) => user_permissions.includes('srp.change_evefleetshipreimbursement'),
    'structures.timers.view': (is_superuser, user_permissions) => !(!is_superuser && !user_permissions.includes('structures.view_evestructuretimer')),
    'structures.timers.view#strict': (_is_superuser, user_permissions) => user_permissions.includes('structures.view_evestructuretimer'),
    'structures.timers.manage': (is_superuser, user_permissions) => !(!is_superuser && !user_permissions.includes('structures.add_evestructuretimer')),
    'structures.timers.verify': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('structures.change_evestructuretimer'),
    'structures.timers.add_button': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('fleets.add_evefleet'),
    'moons.view': (is_superuser, user_permissions) => !(!is_superuser && !user_permissions.includes('moons.view_evemoon')),
    'moons.view#strict': (_is_superuser, user_permissions) => user_permissions.includes('moons.view_evemoon'),
    'moons.manage#strict': (_is_superuser, user_permissions) => user_permissions.includes('moons.add_evemoon'),
    'intel.affiliations': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('intel.change_intelaffiliation'),
    'applications.manage': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('applications.change_evecorporationapplication'),
    'characters.view_staff': (is_superuser, user_permissions) => !(!is_superuser && !user_permissions.includes('eveonline.view_evecharacter')),
    'corporations.members.view_all': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('eveonline.view_evecorporation'),
    'surveys.manage': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('surveys.change_surveycampaign'),
    'surveys.results.view': (is_superuser) => is_superuser,
    'learning.admin': (is_superuser, user_permissions) => is_superuser
        || user_permissions.includes('learning.change_certificate')
        || user_permissions.includes('learning.view_certificate'),
    'skillsets.admin': (is_superuser, user_permissions) => is_superuser
        || user_permissions.includes('eveonline.change_eveskillset')
        || user_permissions.includes('eveonline.view_eveskillset'),
    'tribes.roster.view': (is_superuser, user_permissions) => user_permissions.includes('eveonline.add_evecharactertag') || is_superuser,
    'characters.readiness#strict': (_is_superuser, user_permissions) => user_permissions.includes('eveonline.add_evecharactertag'),
    'industry.industrialists.view': (is_superuser, user_permissions) => is_superuser || user_permissions.includes('eveonline.add_evecharactertag'),
    'industry.industrialists.view#strict': (_is_superuser, user_permissions) => user_permissions.includes('eveonline.add_evecharactertag'),
    'notifications.push#strict': (_is_superuser, user_permissions) => user_permissions.includes('subscriptions.add_usersubscription'),
    'site.debug_pages': (is_superuser) => is_superuser,
    'characters.lookup': (is_superuser) => is_superuser,
    // PageFinder / PageBreadcrumbs: `if (user && user?.is_superuser)` showed every page.
    'site.all_pages': (is_superuser) => is_superuser,
}

const ALL_LEGACY_PERMISSIONS = [...new Set(Object.values(GATES).flatMap((gate) => gate.legacy.perms ?? []))]

describe('gates manifest', () => {
    it('has an inline oracle for every non-custom gate', () => {
        const missing = (Object.keys(GATES) as GateKey[]).filter((gate) => !GATES[gate].legacy.custom && !INLINE[gate])
        expect(missing).toEqual([])
    })

    it('legacy mode answers exactly like the inline checks it replaced', () => {
        const permission_sets = [[], ...ALL_LEGACY_PERMISSIONS.map((perm) => [perm]), ALL_LEGACY_PERMISSIONS]
        for (const [gate, inline] of Object.entries(INLINE) as [GateKey, Inline][]) {
            for (const is_superuser of [false, true]) {
                for (const perms of permission_sets) {
                    const ctx = context({ is_superuser, legacy_permissions: perms })
                    expect(can(ctx, gate), `${gate} superuser=${is_superuser} perms=${perms}`).toBe(inline(is_superuser, perms))
                }
            }
        }
    })

    it('names a parity class on every gate that can differ from its feature', () => {
        for (const [key, gate] of Object.entries(GATES)) {
            if (key.endsWith('#strict')) expect(gate.parity, key).toBe('superuser_gain')
            if (gate.legacy.custom) expect(gate.parity, key).toBe('custom')
        }
    })

    it('every sitemap gate is a manifest gate', () => {
        const unknown = sitemap
            .map((page: any) => page.permissions?.gate)
            .filter((gate) => gate && !(gate in GATES))
        expect(unknown).toEqual([])
    })

    it('every gate used in src is a manifest gate', () => {
        const used = new Set<string>()
        for (const file of source_files(SRC)) {
            for (const match of readFileSync(file, 'utf8').matchAll(/can(?:_custom)?\(\s*\w+\s*,\s*'([^']+)'/g))
                used.add(match[1])
        }
        expect(used.size).toBeGreaterThan(20)
        expect([...used].filter((gate) => !(gate in GATES))).toEqual([])
    })

    it('no source file gates on Django permission strings any more', () => {
        const offenders = source_files(SRC)
            .filter((file) => !file.endsWith('helpers/gates.ts'))
            .filter((file) => /get_user_permissions|user_permissions|permissions\.includes\(/.test(readFileSync(file, 'utf8')))
            .map((file) => relative(SRC, file))
        expect(offenders).toEqual([])
    })
})

describe('can()', () => {
    afterEach(() => reset_gate_mismatch_reporter())

    it('denies everything to anonymous visitors', () => {
        for (const gate of Object.keys(GATES) as GateKey[]) {
            if (GATES[gate].legacy.custom) continue
            expect(can(ANONYMOUS_GATES, gate), gate).toBe(false)
        }
    })

    it('features mode follows the feature, not the legacy permission', () => {
        const ctx = context({
            gate_source: 'features',
            is_superuser: true,
            legacy_permissions: ['fleets.view_evefleet'],
            features: ['campaigns.view'],
        })
        expect(can(ctx, 'fleets.view')).toBe(false)
        expect(can(ctx, 'campaigns.view')).toBe(true)
        // Variants share their feature.
        expect(can(context({ gate_source: 'features', features: ['moons.view'] }), 'moons.view#strict')).toBe(true)
    })

    it('shadow mode acts on legacy and reports each disagreement once', () => {
        const reports: GateMismatch[] = []
        set_gate_mismatch_reporter((report) => reports.push(report))
        const ctx = context({
            gate_source: 'shadow',
            legacy_permissions: ['fleets.view_evefleet'],
            features: ['campaigns.view'],
        })

        expect(can(ctx, 'fleets.view')).toBe(true)
        expect(can(ctx, 'fleets.view')).toBe(true)
        expect(can(ctx, 'campaigns.view')).toBe(false)
        expect(can(ctx, 'posts.create')).toBe(false)

        expect(reports).toEqual([
            { gate: 'fleets.view', feature: 'fleets.view', user_id: 7, legacy: true, feature_allows: false },
            { gate: 'campaigns.view', feature: 'campaigns.view', user_id: 7, legacy: false, feature_allows: true },
        ])
    })

    it('legacy mode never reports', () => {
        const reporter = vi.fn()
        set_gate_mismatch_reporter(reporter)
        can(context({ features: ['fleets.view'] }), 'fleets.view')
        expect(reporter).not.toHaveBeenCalled()
    })

    it('refuses custom gates', () => {
        expect(() => can(context(), 'content.manage')).toThrow(/can_custom/)
    })
})

describe('can_custom()', () => {
    it('uses the supplied legacy check in legacy mode', async () => {
        expect(await can_custom(context(), 'content.manage', async () => true)).toBe(true)
        expect(await can_custom(context({ features: ['content.manage'] }), 'content.manage', async () => false)).toBe(false)
    })

    it('skips the legacy check in features mode', async () => {
        const legacy_check = vi.fn(async () => true)
        expect(await can_custom(context({ gate_source: 'features' }), 'content.manage', legacy_check)).toBe(false)
        expect(legacy_check).not.toHaveBeenCalled()
    })
})

describe('get_gates()', () => {
    afterEach(() => vi.mocked(get_user_gates).mockReset())

    it('does not call the API without a session', async () => {
        expect(await get_gates(astro())).toBe(ANONYMOUS_GATES)
        expect(get_user_gates).not.toHaveBeenCalled()
    })

    it('fetches once per request', async () => {
        vi.mocked(get_user_gates).mockResolvedValue({
            features: ['fleets.view'],
            legacy: { permissions: ['fleets.view_evefleet'], is_superuser: true },
            gate_source: 'shadow',
        })
        const request = astro(token({ user_id: 3, username: 'pilot', is_superuser: false }))

        const [first, second] = await Promise.all([get_gates(request), get_gates(request)])

        expect(first).toBe(second)
        expect(get_user_gates).toHaveBeenCalledTimes(1)
        expect(first.features).toEqual(['fleets.view'])
        expect(first.legacy_permissions).toEqual(['fleets.view_evefleet'])
        // The JWT claim, like the inline checks, not the live flag.
        expect(first.is_superuser).toBe(false)
        expect(first.gate_source).toBe('shadow')
    })

    it('keeps the superuser claim when the API call fails, like the old profile fetch', async () => {
        vi.mocked(get_user_gates).mockRejectedValue(new Error('down'))
        const ctx = await get_gates(astro(token({ user_id: 3, is_superuser: true })))

        expect(ctx.legacy_permissions).toEqual([])
        expect(ctx.gate_source).toBe('legacy')
        expect(can(ctx, 'fleets.view')).toBe(true)
        expect(can(ctx, 'moons.view#strict')).toBe(false)
    })

    it('treats an unreadable token as signed out', async () => {
        expect(await get_gates(astro('not-a-jwt'))).toBe(ANONYMOUS_GATES)
        expect(get_user_gates).not.toHaveBeenCalled()
    })

    it('falls back to legacy for an unknown gate source', () => {
        const ctx = gate_context_from(
            { user_id: 1, username: 'x', avatar: '', is_superuser: false, permissions: [] },
            { features: [], legacy: { permissions: [], is_superuser: false }, gate_source: 'nonsense' as any },
        )
        expect(ctx.gate_source).toBe('legacy')
    })
})
