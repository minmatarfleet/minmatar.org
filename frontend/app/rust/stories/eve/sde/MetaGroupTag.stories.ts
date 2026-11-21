import { expect, within } from 'storybook/test'
import MetaGroupTag from '@components/blocks/sde/MetaGroupTag.astro'
import { select_control } from '../../_controls'

type Ctx = { canvasElement: HTMLElement }

const META_GROUPS = ['Tech I', 'Tech II', 'Tech III', 'Storyline', 'Faction', 'Deadspace', 'Officer', 'Abyssal', 'Premium'] as const

const tag = (canvasElement: HTMLElement) => canvasElement.querySelector('.meta-group-tag') as HTMLElement

const colour_play = (name: string, token: string) => async ({ canvasElement }: Ctx) => {
    const element = tag(canvasElement)
    await expect(within(canvasElement).getByText(name)).toBeVisible()
    await expect(element).toHaveAttribute('data-meta-group', token)
    await expect(element.getAttribute('style')).toContain(`--tag_color: var(--${token})`)
}

export default {
    title: 'EVE/SDE/MetaGroupTag',
    component: MetaGroupTag,
    parameters: {
        docs: {
            description: {
                component: [
                    'The meta group of an item (Tech I, Tech II, Faction, Deadspace, Officer...) as a small tag in the meta colour tokens (`--tech-i`, `--tech-ii`, `--faction`...), the same colours FittingSlot uses for module borders. TypeRow puts it after the name.',
                    'It renders nothing when `meta_group_name` is empty: the SDE has no meta group for most non-modules, and calling that "Tech I" would be wrong for a blueprint or ore. Meta groups without a colour token (Premium, Structure Tech I) get a neutral outline tag. Tech I is light, so its text is `--background`.',
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        meta_group_name: select_control(META_GROUPS, 'Meta group name from the SDE (`invMetaGroups.metaGroupName`).'),
        narrow: { control: 'boolean', description: 'Less padding, for inline use after a name.' },
    },
    args: {
        meta_group_name: 'Tech II',
        narrow: true,
    },
}

export const TechII = {
    name: 'Tech II',
    play: async (context: Ctx) => colour_play('Tech II', 'tech-ii')(context),
}

export const TechI = {
    name: 'Tech I (dark text)',
    args: { meta_group_name: 'Tech I' },
    play: async (context: Ctx) => {
        await colour_play('Tech I', 'tech-i')(context)
        await expect(tag(context.canvasElement).getAttribute('style')).toContain('--badge_color: var(--background)')
    },
}

export const Faction = {
    args: { meta_group_name: 'Faction' },
    play: async (context: Ctx) => colour_play('Faction', 'faction')(context),
}

export const Deadspace = {
    args: { meta_group_name: 'Deadspace' },
    play: async (context: Ctx) => colour_play('Deadspace', 'deadspace')(context),
}

export const Officer = {
    args: { meta_group_name: 'Officer' },
    play: async (context: Ctx) => colour_play('Officer', 'officer')(context),
}

export const Storyline = {
    args: { meta_group_name: 'Storyline' },
    play: async (context: Ctx) => colour_play('Storyline', 'storyline')(context),
}

export const TechIII = {
    name: 'Tech III',
    args: { meta_group_name: 'Tech III' },
    play: async (context: Ctx) => colour_play('Tech III', 'tech-iii')(context),
}

export const WithoutColourToken = {
    name: 'No colour token (Premium)',
    args: { meta_group_name: 'Premium' },
    play: async ({ canvasElement }: Ctx) => {
        const element = tag(canvasElement)
        await expect(element).toHaveClass('tag--outline')
        await expect(element).toHaveAttribute('data-meta-group', 'other')
        await expect(element).toHaveTextContent('Premium')
    },
}

export const NoMetaGroup = {
    name: 'No meta group: renders nothing',
    args: { meta_group_name: null },
    parameters: { rust: { allow_empty: true } },
    play: async ({ canvasElement }: Ctx) => {
        await expect(canvasElement.querySelector('.meta-group-tag')).toBeNull()
    },
}
