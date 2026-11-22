import { expect, within } from 'storybook/test'
import CampaignRolesPanel from '@components/blocks/CampaignRolesPanel.astro'
import { campaign_discord_roles, campaign_roles_typical, campaign_roles_unsynced } from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

/** One role's row; collapsed rows keep their bodies in the DOM. */
const row = (canvasElement: HTMLElement, kind: string) => within(canvasElement.querySelector(`[data-role="${kind}"]`) as HTMLElement)

const BASE_ARGS = {
    part_url: '/partials/campaign_roles_component?slug=operation-anvil',
    search_url: '/partials/campaign_character_search_component',
}

export default {
    title: 'Features/Campaigns/CampaignRolesPanel',
    component: CampaignRolesPanel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Roles tab of `/campaigns/<slug>/`: the four campaign roles (Coordinator, FC, Diplomat, Recon) held on the coordination Discord, with a member count each. A row opens to its holders: portrait, corporation, alliance and Discord name, tagged "Not signed in" (Discord only) or "Gets the role once they link Discord" (added on the site).',
                    'Managers and Coordinators add someone with a character Combobox and remove them; managers also pick the Discord role behind each campaign role. FCs, Diplomats and Recon read it only. Every action posts to `part_url` (`campaign_roles_component`) and swaps the panel.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        roles: { control: 'object', description: 'From `GET /api/campaigns/<slug>/roles`.' },
        can_change: { control: 'boolean', description: 'Managers and Coordinators: add, remove, Sync now.' },
        can_map: { control: 'boolean', description: 'Managers: the Discord role picker.' },
        open_kind: { control: 'text', description: 'The role row shown open.' },
    },
    args: { ...BASE_ARGS, roles: campaign_roles_typical, open_kind: 'fc' },
}

export const ReadOnly = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'Roles – 4' })).toBeVisible()
        await expect(canvasElement.querySelectorAll('[data-role]')).toHaveLength(4)
        // The open FC row lists its three holders and their states.
        await expect(canvas.getByText('Henri Gray')).toBeVisible()
        await expect(canvas.getByText('Not signed in')).toBeVisible()
        await expect(canvas.getByText('Gets the role once they link Discord')).toBeVisible()
        await expect(canvas.queryByRole('button', { name: 'Sync now' })).toBeNull()
        await expect(canvas.queryByRole('button', { name: /^Remove / })).toBeNull()
        await expect(canvas.queryByRole('combobox')).toBeNull()
    },
}

export const Coordinator = {
    args: { can_change: true },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('button', { name: 'Sync now' })).toBeVisible()
        await expect(canvas.getByRole('button', { name: 'Remove Henri Gray' })).toBeVisible()
        const fc = row(canvasElement, 'fc')
        // Each role's picker has its own id, so its label names it.
        await expect(fc.getByRole('combobox', { name: 'Add a FC by character name' })).toHaveAttribute('id', 'campaign-role-add-fc-input')
        // Coordinators cannot point a role at another Discord role.
        await expect(canvas.queryAllByLabelText('Discord role')).toHaveLength(0)
    },
}

export const Manager = {
    args: { can_change: true, can_map: true, discord_roles: campaign_discord_roles },
    play: async ({ canvasElement }: Ctx) => {
        const picker = canvasElement.querySelector('[data-role="fc"] select') as HTMLSelectElement
        await expect(picker).toBeVisible()
        // The role's current Discord role is the one marked selected.
        await expect(picker.querySelector('option[selected]')?.textContent).toBe('FC')
        await expect(picker.options).toHaveLength(campaign_discord_roles.length + 1)
    },
}

export const NotSynced = {
    args: { roles: campaign_roles_unsynced, can_change: true, can_map: true, discord_roles: campaign_discord_roles },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByText('Not synced yet')).toBeVisible()
        const fc = row(canvasElement, 'fc')
        await expect(fc.getByText('Nobody holds this role')).toBeVisible()
        await expect(fc.getByText('No Discord role picked')).toBeVisible()
    },
}

export const ActionError = {
    args: { can_change: true, error_message: 'No character has that exact name.' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('alert')).toHaveTextContent('No character has that exact name.')
    },
}
