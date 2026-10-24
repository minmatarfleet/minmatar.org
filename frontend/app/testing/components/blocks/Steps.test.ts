import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import Steps from '@components/blocks/Steps.astro'

async function render(props: Record<string, unknown>) {
    const container = await AstroContainer.create()
    return container.renderToString(Steps, { props })
}

test('Steps renders the subtitle it is given', async () => {
    const html = await render({ step: 2, title: 'Paste', subtitle: 'En el juego' })
    expect(html).toContain('En el juego')
    expect(html).not.toContain('In-game')
})

test('Steps leaves the subtitle out when there is none', async () => {
    const html = await render({ step: 1, title: 'Paste' })
    expect(html).not.toContain('<small')
})
