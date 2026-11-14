import { experimental_AstroContainer as AstroContainer } from 'astro/container'
import { expect, test } from 'vitest'
import LearningCertificateDetail from '@components/blocks/LearningCertificateDetail.astro'
import type { LearningCertificate } from '@dtypes/api.minmatar.org'

const certificate: LearningCertificate = {
    slug: 'fw-basics',
    title: 'FW Basics',
    summary: 'Learn militia fundamentals.',
    sort_order: 1,
    personas: ['militia'],
    learning_count: 1,
    learnings: [
        {
            slug: 'fw-plexing',
            title: 'Plexing',
            summary: 'How to plex.',
            url: 'https://wiki.minmatar.org/plexing',
            content_kind: 'guide',
            thumbnail_url: '',
            estimated_minutes: 10,
            order: 1,
        },
    ],
    required_certificates: [],
    required_count: null,
}

test('Open is a button without href/target so tip modal is not raced by native navigation', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(LearningCertificateDetail, {
        props: {
            certificate,
            completed_slugs: [],
            auth_token: '',
            percent: 0,
        },
    })

    expect(result).toMatch(/x-on:click\.prevent="openLearning\(&#34;https:\/\/wiki\.minmatar\.org\/plexing&#34;\)"/)
    expect(result).toMatch(/<button[^>]*class="\[ button \] \[ learning-card__open \]"/)
    expect(result).not.toMatch(/href="https:\/\/wiki\.minmatar\.org\/plexing"/)
    expect(result).not.toMatch(/learning-card__open[^>]*target="_blank"/)
})

test('A certificate earned through others lists them and marks the ones held', async () => {
    const container = await AstroContainer.create()
    const result = await container.renderToString(LearningCertificateDetail, {
        props: {
            certificate: {
                ...certificate,
                slug: 'fleet-roles',
                learnings: [],
                learning_count: 0,
                required_certificates: [
                    { slug: 'fleet-role-damage', title: 'Damage' },
                    { slug: 'fleet-role-remote-repair', title: 'Remote Repair' },
                ],
                required_count: 1,
            },
            completed_slugs: [],
            auth_token: '',
            percent: 100,
            held_slugs: ['fleet-role-damage'],
        },
    })
    expect(result).toContain('Earn any 1 of these certificates')
    expect(result).toContain('/learning/certificates/fleet-role-remote-repair/')
    expect(result).toMatch(/data-held="true"[^>]*>\s*<span[^>]*>✓/)
})
