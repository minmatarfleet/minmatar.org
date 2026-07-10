/** Field keys shared by {@link CorporationApplicationRequirements} across all corp apply forms. */
export const CORPORATION_APPLICATION_REQUIREMENT_FIELD_KEYS = [
    'agree_tenets',
    'confirm_omega',
    'confirm_auth_chars',
] as const;

export function corporationApplicationFieldName(
    formPrefix: string,
    includeFieldNames: boolean,
    key: string,
): string | undefined {
    return includeFieldNames ? `${formPrefix}${key}` : undefined;
}
