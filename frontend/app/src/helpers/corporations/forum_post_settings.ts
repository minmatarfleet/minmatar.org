import type { CorporationForumPost } from '@dtypes/api.minmatar.org'
import type { ui } from '@i18n/ui'

type UiKey = keyof typeof ui['en']

export const RECRUITMENT_CENTER_URL = 'https://forums.eveonline.com/c/corporations-alliances/recruitment-center/63'

export type ForumPostAction = 'save' | 'remove'

export interface ForumPostFlash {
    kind: 'success' | 'error';
    key: UiKey;
}

export function parse_forum_post_action(value: unknown): ForumPostAction {
    return value === 'remove' ? 'remove' : 'save'
}

// Codes from the backend's recruitment.forums / recruitment.forum_posts.
const SAVE_ERRORS: Record<string, UiKey> = {
    url_required: 'corporations.forum_post.error_url_required',
    invalid_url: 'corporations.forum_post.error_invalid_url',
    not_eve_forums: 'corporations.forum_post.error_not_eve_forums',
    not_a_thread: 'corporations.forum_post.error_not_a_thread',
    not_recruitment_center: 'corporations.forum_post.error_not_recruitment_center',
    thread_not_found: 'corporations.forum_post.error_thread_not_found',
    thread_linked_elsewhere: 'corporations.forum_post.error_thread_linked_elsewhere',
}

export function forum_post_error_key(code: string): UiKey {
    return SAVE_ERRORS[code] ?? 'corporations.settings.error_save'
}

/** The thread's title, or its URL when the forum couldn't be read. */
export function forum_post_link_text(post: Pick<CorporationForumPost, 'title' | 'url'>): string {
    return post.title || post.url || ''
}

/** One line for the collapsed forum section header. */
export function forum_post_section_summary(
    post: Pick<CorporationForumPost, 'exists' | 'title'>,
    labels: { not_linked: string, linked: string },
): string {
    if (!post.exists)
        return labels.not_linked
    return post.title ? `${labels.linked} · ${post.title}` : labels.linked
}
