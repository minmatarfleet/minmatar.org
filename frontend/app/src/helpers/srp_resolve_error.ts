const CHARACTER_NOT_ON_ACCOUNT = 'Character does not belong to user'

export function srp_resolve_blocked_message(
    fetching_error: { message: string } | false,
    external_killmail_link: string | null,
    _program: string | null,
    translate: (key: string) => string,
): string {
    if (fetching_error && fetching_error.message.includes(CHARACTER_NOT_ON_ACCOUNT))
        return translate('srp_character_not_on_account')
    if (fetching_error)
        return fetching_error.message
    if (!external_killmail_link)
        return translate('invalid_killmail_link')
    return translate('invalid_srp_program')
}

export function srp_resolve_is_blocked(
    fetching_error: { cause?: unknown } | false,
    external_killmail_link: string | null,
    program: string | null,
): boolean {
    return Boolean(
        (fetching_error && fetching_error.cause) ||
        !external_killmail_link ||
        !program
    )
}
