import { expect, within, waitFor } from 'storybook/test'
import PropagandaPostCard from '@components/blocks/PropagandaPostCard.astro'
import { post_metropolis, post_group, post_alliance, posts_by_state, EDITOR_ID } from '../../../fixtures/features/content'

// Entrance animations (up to ~1s of delay plus duration) start at opacity 0, so wait for them to settle before asserting visibility.
const settle = (check: () => unknown) => waitFor(check, { timeout: 3000 })

const [draft, published, trashed, members] = posts_by_state

export default {
    title: 'Features/Content/PropagandaPostCard',
    component: PropagandaPostCard,
    parameters: {
        docs: {
            description: {
                component: [
                    'A poster card: the post image (or the author portrait), date, title and, for group posts, the group chip. In the public view the whole card is one link; in the editor view it shows the post state and, on your own posts, the publish / edit / trash actions.',
                    'It is the card in the posters reel on the content pages (the content grids use the lighter PropagandaPostCardOrg). The scenarios show the public card, a group post, and the editor view for a draft, a published post, a trashed post (desaturated) and someone else\'s post (no actions).',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        post: { control: 'object', description: 'The post (PostListUI).' },
        editor_id: { control: 'number', description: 'The signed-in user id; actions only show on posts they own.' },
        is_editing: { control: 'boolean', description: 'Editor view: state tag, actions, no whole-card link.' },
        zoomable: { control: 'boolean', description: 'Click the picture to zoom it instead of following the card link.' },
    },
    args: { post: post_metropolis, is_editing: false },
}

export const PublicCard = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await settle(() => expect(canvas.getByRole('heading', { name: post_metropolis.title })).toBeVisible())
        await expect(canvasElement.querySelector('.propaganda-post-card__hitbox')).toHaveAttribute('href', '/alliance/propaganda/1401')
        // No author image, so the portrait is the cover.
        await expect(canvasElement.querySelector('img[src*="2112954532"]')).not.toBeNull()
        // Public view carries no state tag.
        await expect(canvas.queryByText('Published')).toBeNull()
    },
}

export const GroupPost = {
    args: { post: post_group },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.textContent).toContain(post_group.author.character_name)
        await expect(canvasElement.textContent).toContain('Dreadnoughts')
    },
}

export const AlliancePost = {
    args: { post: post_alliance },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await settle(() => expect(within(canvasElement).getByRole('heading', { name: post_alliance.title })).toBeVisible())
        await expect(canvasElement.querySelector('.propaganda-post-card__hitbox')).toHaveAttribute('href', '/alliance/propaganda/1395')
    },
}

export const EditingOwnDraft = {
    args: { post: draft, is_editing: true, editor_id: EDITOR_ID },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvasElement.querySelector('#post-tag-1601')).not.toBeNull()
        // The post actions sit in the card's hover-revealed actions (opacity 0 until hover), so they are only in the DOM here.
        await expect(canvas.getByRole('button', { name: 'Publish' })).toBeInTheDocument()
        // The editor view leaves the whole-card link out so the actions stay clickable.
        await expect(canvasElement.querySelector('.propaganda-post-card__hitbox')).toBeNull()
    },
}

export const EditingPublished = {
    args: { post: published, is_editing: true, editor_id: EDITOR_ID },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const canvas = within(canvasElement)
        await expect(canvas.queryByRole('button', { name: 'Publish' })).toBeNull()
        await expect(canvasElement.querySelector('#post-tag-1600')).not.toBeNull()
    },
}

export const EditingTrashed = {
    args: { post: trashed, is_editing: true, editor_id: EDITOR_ID },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('[data-desature="mild"]')).not.toBeNull()
        // Hover-revealed post actions, as above: in the DOM, not visible until hover.
        await expect(within(canvasElement).getByRole('button', { name: 'Publish' })).toBeInTheDocument()
    },
}

export const EditingMembersOnlyGroupPost = {
    args: { post: members, is_editing: true, editor_id: EDITOR_ID },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.textContent).toContain('Dreadnoughts')
        await expect(canvasElement.querySelector('.visibility-tag')).not.toBeNull()
    },
}

export const EditingSomeoneElsesPost = {
    args: { post: published, is_editing: true, editor_id: 999 },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.querySelector('button')).toBeNull()
        await expect(canvasElement.querySelector('#post-tag-1600')).not.toBeNull()
    },
}
