import scout_links from '@json/scout-links.json'

const SCOUT_LINKS = scout_links as Record<string, string>

export function is_scout_link_target(target: string): boolean {
    return Object.prototype.hasOwnProperty.call(SCOUT_LINKS, target)
}

/**
 * Where a recruitment scout link (/go/<code>/<target>) lands. Unknown targets
 * go to the home page so a mistyped link still lands somewhere useful.
 */
export function scout_link_destination(target: string): string {
    return is_scout_link_target(target) ? SCOUT_LINKS[target] : '/'
}
