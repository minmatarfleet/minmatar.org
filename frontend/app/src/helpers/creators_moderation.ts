/** Labels for the creator moderation screen. */
import type { CreatorModerationAccountRow } from '@helpers/api.minmatar.org/creators_moderation'

/** Columns in the creators table, chevron excluded. */
export const CREATOR_COLUMNS = 5

/** Items load this many at a time in an open creator row. */
export const CREATOR_ITEMS_PAGE = 10

/** The creator's main's name, or their site username. */
export const creator_name = (account: CreatorModerationAccountRow): string =>
    account.character_name || account.username

/** The account's handle on its platform (u/name on Reddit), or `fallback`
 *  ("YouTube channel") when the platform gave no name. */
export function creator_handle(account: CreatorModerationAccountRow, fallback: string): string {
    if (!account.platform_username) return fallback
    return account.provider === 'reddit' ? `u/${account.platform_username}` : account.platform_username
}

/** Does the account match a search over names and handles? */
export function creator_matches(account: CreatorModerationAccountRow, query: string): boolean {
    if (!query) return true
    const needle = query.toLowerCase()
    return [account.character_name ?? '', account.username, account.platform_username]
        .some((text) => text.toLowerCase().includes(needle))
}
