import { expect, userEvent, waitFor, within } from 'storybook/test'
import CampaignCoordinatorsPanel from '@components/blocks/CampaignCoordinatorsPanel.astro'
import {
    campaign_coordination_members,
    campaign_coordination_no_server,
    campaign_coordinator_roles,
    campaign_legacy_coordinators,
} from '../../../fixtures/features/campaigns'

type Ctx = { canvasElement: HTMLElement }

const BASE_ARGS = {
    part_url: '/partials/campaign_settings_component/?slug=operation-anvil&part=coordinators',
    search_url: '/partials/campaign_character_search_component',
}

/** The rows a viewer can see (Alpine hides filtered ones with display: none). */
const shown = (canvasElement: HTMLElement) =>
    [...canvasElement.querySelectorAll<HTMLElement>('[data-search]')].filter((row) => row.style.display !== 'none')

export default {
    title: 'Features/Campaigns/CampaignCoordinatorsPanel',
    component: CampaignCoordinatorsPanel,
    parameters: {
        docs: {
            description: {
                component: [
                    'The Coordinators section of a campaign\'s Settings tab. **People with access** lists role holders (Coordinator, FC, Diplomat, Recon) with a role tag and a status tag, plus coordinators invited before roles. Invite anyone by character and role; what each role sees and changes opens on demand.',
                    '**On the coordination Discord** lists the members of the campaign\'s own server, grouped by the tag in their server name, each with the character we found and how sure that is: Linked, the tag matches, a name match only, a name twin outside their tag (they must name the character), or nothing. People with a role hide behind a switch; the search filters the rendered rows. Every action posts the Settings form to `part_url`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        roles: { control: 'object', description: 'From `GET /api/campaigns/<slug>/roles`.' },
        coordinators: { control: 'object', description: 'Coordinators invited before roles (`CampaignSettings.coordinators`).' },
        discord: { control: 'object', description: 'From `GET /api/campaigns/<slug>/roles/suggestions`; null when Discord could not say.' },
    },
    args: { ...BASE_ARGS, roles: campaign_coordinator_roles, discord: campaign_coordination_members },
}

export const Coalition = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await expect(canvas.getByRole('heading', { name: 'People with access' })).toBeVisible()
        await expect(canvas.getByRole('heading', { name: 'On the coordination Discord – 14' })).toBeVisible()
        // Grouped by tag, untagged last.
        const groups = [...canvasElement.querySelectorAll('h5')].map((h) => h.textContent?.replace(/\s+/g, ' ').trim())
        await expect(groups).toEqual(['[CAMELOT] 1', '[COA] 2', '[FL33T] 6', '[FRONT] 4', 'No tag 1'])
        // A name twin outside the tag is flagged and needs the character named.
        await expect(canvas.getByText('Not in [FRONT]')).toBeVisible()
        await expect(canvas.getByLabelText('The character [FRONT] Crispy flies')).toBeVisible()
        // The site-only Diplomat says why Discord has not given the role.
        await expect(canvas.getByText('No Discord role')).toBeVisible()
    },
}

export const RoleHoldersHidden = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // Five members already hold a role: hidden until the switch is on.
        await expect(shown(canvasElement)).toHaveLength(9)
        await userEvent.click(canvas.getByRole('checkbox', { name: 'Show the 5 who have a role' }))
        // Alpine re-renders on its next tick in a real browser.
        await waitFor(() => expect(shown(canvasElement)).toHaveLength(14))
    },
}

export const SearchFiltersRows = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        await userEvent.type(canvas.getByRole('searchbox', { name: 'Find someone' }), 'cryonic')
        // Mudaro Rogers holds a role, so only Skora Vel shows.
        await waitFor(() => expect(shown(canvasElement).map((row) => row.textContent)).toEqual([expect.stringContaining('Skora Vel')]))
    },
}

export const FilterByRole = {
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        const access = canvasElement.querySelector('[aria-labelledby="campaign-coordinators-access"]') as HTMLElement
        const visible = () => [...access.querySelectorAll<HTMLElement>('[data-role]')].filter((row) => row.style.display !== 'none')
        await expect(visible()).toHaveLength(5)
        await userEvent.click(canvas.getByRole('radio', { name: /^FC/ }))
        await waitFor(() => expect(visible().map((row) => row.dataset.role)).toEqual(['fc', 'fc']))
        await userEvent.click(canvas.getByRole('radio', { name: /^IT/ }))
        await waitFor(() => expect(visible().map((row) => row.dataset.role)).toEqual(['it']))
        await userEvent.click(canvas.getByRole('radio', { name: /^Everyone/ }))
        await waitFor(() => expect(visible()).toHaveLength(5))
    },
}

export const WithInvitedCoordinators = {
    args: { coordinators: campaign_legacy_coordinators, coordinator_scopes: ['sides', 'timers'] },
    play: async ({ canvasElement }: Ctx) => {
        const canvas = within(canvasElement)
        // A row tag and a filter chip of its own.
        await expect(canvas.getAllByText('Invited coordinator')).toHaveLength(2)
        await expect(canvas.getByRole('radio', { name: /^Invited coordinator/ })).toBeInTheDocument()
        await expect(canvas.getByRole('group', { name: 'Invited coordinators see' })).toBeVisible()
    },
}

export const NoCoordinationServer = {
    args: { discord: campaign_coordination_no_server },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByText('No coordination server yet')).toBeVisible()
    },
}

export const ActionError = {
    args: { error_message: 'Pick a role.' },
    play: async ({ canvasElement }: Ctx) => {
        await expect(within(canvasElement).getByRole('alert')).toHaveTextContent('Pick a role.')
    },
}
