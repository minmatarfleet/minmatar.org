/** SKINs and blueprints stay out of ranked sales surfaces. */

export function is_skin_or_blueprint(row: { name: string }): boolean {
    return /\bSKIN\b/i.test(row.name) || /blueprint/i.test(row.name)
}

export function without_skins_and_blueprints<T extends { name: string }>(rows: readonly T[]): T[] {
    return rows.filter((row) => !is_skin_or_blueprint(row))
}

export function without_empty_class_buckets<T extends { name: string }>(
    by_class: Readonly<Record<string, readonly T[]>>,
): Record<string, T[]> {
    return Object.fromEntries(
        Object.entries(by_class)
            .map(([name, rows]) => [name, without_skins_and_blueprints(rows)] as const)
            .filter(([, rows]) => rows.length > 0),
    )
}
