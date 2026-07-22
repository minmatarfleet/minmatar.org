import type { Fitting, KnownFittingKey } from '@dtypes/api.minmatar.org'

export type GuideFittingRef = {
    id: string
    knownKey?: KnownFittingKey | null
    fittingId: number
    name: string
    description: string
    eftFormat: string
}

export type ResolvedGuideFitting<T extends GuideFittingRef = GuideFittingRef> = T & {
    resolvedFittingId: number
    resolvedEftFormat: string
    fromLibrary: boolean
}

/** Attach the guide catalog key when authors omit it (prefix + local id). */
export function withGuideKnownKey<T extends GuideFittingRef>(
    fit: T,
    keyPrefix: string,
): T & { knownKey: KnownFittingKey } {
    const knownKey = (fit.knownKey ?? `${keyPrefix}.${fit.id}`) as KnownFittingKey
    return { ...fit, knownKey }
}

/**
 * Resolve a guide fit against the live library.
 * Prefer known_key (stable across envs), then fittingId if that row exists
 * in the current API response, else keep the static guide EFT / no link.
 */
export function resolveGuideFitting<T extends GuideFittingRef>(
    fit: T,
    library: Fitting[],
): ResolvedGuideFitting<T> {
    if (fit.knownKey) {
        const byKey = library.find((row) => row.known_key === fit.knownKey)
        if (byKey) {
            return {
                ...fit,
                resolvedFittingId: byKey.id,
                resolvedEftFormat: byKey.eft_format,
                fromLibrary: true,
            }
        }
    }

    if (fit.fittingId > 0) {
        const byId = library.find((row) => row.id === fit.fittingId)
        if (byId) {
            return {
                ...fit,
                resolvedFittingId: byId.id,
                resolvedEftFormat: byId.eft_format,
                fromLibrary: true,
            }
        }
    }

    return {
        ...fit,
        resolvedFittingId: 0,
        resolvedEftFormat: fit.eftFormat,
        fromLibrary: false,
    }
}

export function resolveGuideFittings<T extends GuideFittingRef>(
    fits: T[],
    library: Fitting[],
): ResolvedGuideFitting<T>[] {
    return fits.map((fit) => resolveGuideFitting(fit, library))
}
