import type { User } from '@dtypes/jwt'
import type { GateSource, LedCorporation, UserGates } from '@dtypes/api.minmatar.org'
import { get_user_gates } from '@helpers/api.minmatar.org/gates'
import { get_request_user } from '@helpers/request_user'
import feature_gates from '@json/feature_gates.json'

/**
 * Site gates. Each gate names the pilot feature that owns it and the
 * Django-permission expression it replaced (src/json/feature_gates.json).
 * The backend's gate_source decides which of the two the site acts on:
 * - legacy:   the old expression, exactly as the inline checks computed it
 * - shadow:   legacy, but report every gate where the feature disagrees
 * - features: the pilot feature
 */

export type GateKey = keyof typeof feature_gates.gates

export interface GateLegacy {
    perms?:     string[];
    superuser?: boolean;
    custom?:    boolean;
}

export interface GateDefinition {
    feature: string;
    legacy:  GateLegacy;
    parity?: string;
    note?:   string;
}

export interface GateContext {
    user_id:            number | null;
    features:           string[];
    legacy_permissions: string[];
    /** JWT claim, which is what the inline checks read. */
    is_superuser:       boolean;
    gate_source:        GateSource;
    /** Alliance corporations the user is CEO or a director of, CEO first. */
    led_corporations:   LedCorporation[];
    reported?:          Set<string>;
}

export const GATES = feature_gates.gates as Record<GateKey, GateDefinition>

export const ANONYMOUS_GATES: GateContext = {
    user_id: null,
    features: [],
    legacy_permissions: [],
    is_superuser: false,
    gate_source: 'legacy',
    led_corporations: [],
}

const GATE_SOURCES: GateSource[] = ['legacy', 'shadow', 'features']

export function gate_context_from(user: User | false, gates: UserGates | null): GateContext {
    if (!user) return ANONYMOUS_GATES

    return {
        user_id: user.user_id ?? null,
        features: gates?.features ?? [],
        legacy_permissions: gates?.legacy?.permissions ?? [],
        is_superuser: Boolean(user.is_superuser),
        gate_source: GATE_SOURCES.includes(gates?.gate_source as GateSource) ? gates?.gate_source as GateSource : 'legacy',
        led_corporations: gates?.led_corporations ?? [],
        reported: new Set(),
    }
}

interface AstroLike {
    cookies: { has(name: string): boolean; get(name: string): { value: string } | undefined };
    locals: Record<string, any>;
}

const LOCALS_KEY = 'gates_promise'

/** The signed-in user's gate context, fetched at most once per request. */
export function get_gates(astro: AstroLike): Promise<GateContext> {
    if (!astro.locals[LOCALS_KEY])
        astro.locals[LOCALS_KEY] = load_gates(astro)

    return astro.locals[LOCALS_KEY]
}

async function load_gates(astro: AstroLike): Promise<GateContext> {
    const { auth_token, user } = get_request_user(astro)
    if (!auth_token || !user) return ANONYMOUS_GATES

    let gates: UserGates | null = null
    try {
        gates = await get_user_gates(auth_token)
    } catch (error) {
        // Same as the old profile fetch failing: no permissions, superuser
        // claim still honoured by legacy expressions.
        console.log(error)
    }

    return gate_context_from(user, gates)
}

export function legacy_allows(ctx: GateContext, gate: GateKey): boolean {
    const legacy = GATES[gate].legacy
    if (legacy.superuser && ctx.is_superuser) return true
    return (legacy.perms ?? []).some((perm) => ctx.legacy_permissions.includes(perm))
}

/**
 * The JWT superuser claim, for custom legacy checks (can_custom) whose old
 * rule included it. Read it through here so gates.ts stays the one place
 * that maps the claim.
 */
export function legacy_superuser(ctx: GateContext): boolean {
    return ctx.is_superuser
}

export function feature_allows(ctx: GateContext, gate: GateKey): boolean {
    return ctx.features.includes(GATES[gate].feature)
}

export type GateMismatchReporter = (report: GateMismatch) => void

export interface GateMismatch {
    gate:    GateKey;
    feature: string;
    user_id: number | null;
    legacy:  boolean;
    feature_allows: boolean;
}

let mismatch_reporter: GateMismatchReporter = default_mismatch_reporter

export function set_gate_mismatch_reporter(reporter: GateMismatchReporter) {
    mismatch_reporter = reporter
}

export function reset_gate_mismatch_reporter() {
    mismatch_reporter = default_mismatch_reporter
}

function default_mismatch_reporter(report: GateMismatch) {
    console.warn(`gate-mismatch:${report.gate}`, JSON.stringify(report))
    import('@sentry/astro')
        .then((Sentry) => Sentry.captureMessage(`gate-mismatch:${report.gate}`, {
            level: 'warning',
            fingerprint: [`gate-mismatch:${report.gate}`],
            tags: {
                gate: report.gate,
                feature: report.feature,
                legacy: String(report.legacy),
                feature_allows: String(report.feature_allows),
            },
            extra: { user_id: report.user_id },
        }))
        .catch(() => {})
}

function decide(ctx: GateContext, gate: GateKey, legacy: () => boolean): boolean {
    if (ctx.gate_source === 'features')
        return feature_allows(ctx, gate)

    const legacy_result = legacy()

    if (ctx.gate_source === 'shadow') {
        const feature_result = feature_allows(ctx, gate)
        if (feature_result !== legacy_result && !ctx.reported?.has(gate)) {
            ctx.reported?.add(gate)
            mismatch_reporter({
                gate,
                feature: GATES[gate].feature,
                user_id: ctx.user_id,
                legacy: legacy_result,
                feature_allows: feature_result,
            })
        }
    }

    return legacy_result
}

/** Whether the gate is open for this user. */
export function can(ctx: GateContext, gate: GateKey): boolean {
    if (GATES[gate].legacy.custom)
        throw new Error(`Gate ${gate} has a custom legacy check; use can_custom()`)

    return decide(ctx, gate, () => legacy_allows(ctx, gate))
}

/**
 * For gates whose old check was more than permission strings. The legacy
 * check only runs when its answer is needed (legacy and shadow modes).
 */
export async function can_custom(
    ctx: GateContext,
    gate: GateKey,
    legacy_check: () => boolean | Promise<boolean>,
): Promise<boolean> {
    if (ctx.gate_source === 'features')
        return feature_allows(ctx, gate)

    const legacy_result = Boolean(await legacy_check())
    return decide(ctx, gate, () => legacy_result)
}
