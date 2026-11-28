import { expect } from 'storybook/test'
import ButtonCorpApply from '@components/blocks/ButtonCorpApply.astro'
import { a_rat, a_rat_blocked } from '../../../fixtures/features/corporations-and-tribes'

export default {
    title: 'Features/Corporations and tribes/ButtonCorpApply',
    component: ButtonCorpApply,
    parameters: {
        docs: {
            description: {
                component: [
                    "The corporation page's Enlist today button and its full-screen application dialog. The form posts to `corporation_slide_request_status_item`, which swaps the header's apply status.",
                    "When the pilot fails a required recruitment check (`requirements_blocked`), the dialog ends with a warning listing the unmet rules (`requirements_unmet`) and a checkbox. Apply anyway, and the `override_requirements` field, stay disabled until the box is ticked; the recruiter is then warned on the application.",
                ].join('\n\n'),
            },
        },
    },
    argTypes: {
        corporation: { control: 'object', description: 'CorporationObject; `requirements_blocked` and `requirements_unmet` turn on the Apply anyway warning.' },
        hidden: { control: 'boolean', description: 'Render the dialog without its trigger button.' },
    },
    args: { corporation: a_rat, hidden: false },
}

export const Default = {
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        await expect(canvasElement.innerHTML).toContain('x-bind:disabled="error || !acknowledged"')
        await expect(canvasElement.innerHTML).not.toContain('override_requirements')
    },
}

export const RequirementsBlocked = {
    args: { corporation: a_rat_blocked },
    play: async ({ canvasElement }: { canvasElement: HTMLElement }) => {
        const html = canvasElement.innerHTML
        await expect(html).toContain('name="override_requirements"')
        await expect(html).toContain('Fly our Cruisers doctrine')
        await expect(html).toContain('want to apply anyway')
        await expect(html).toContain('Apply anyway')
    },
}
