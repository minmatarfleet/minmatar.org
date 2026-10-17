export function corporationApplicationFieldName(
    formPrefix: string,
    includeFieldNames: boolean,
    key: string,
): string | undefined {
    return includeFieldNames ? `${formPrefix}${key}` : undefined;
}
