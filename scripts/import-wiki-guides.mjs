#!/usr/bin/env node
/**
 * One-off script: convert wiki-guides-export.json into markdown guide files.
 * Run from repo root: node scripts/import-wiki-guides.mjs
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '..')
const require = createRequire(join(repoRoot, 'frontend/app/package.json'))
const cheerio = require('cheerio')
const exportPath = join(repoRoot, 'wiki-guides-export.json')
const guidesDir = join(repoRoot, 'frontend/app/src/markdown/guides')

const WIKI_BASE = 'https://wiki.minmatar.org'

/** wiki slug path -> local URL slug */
const SLUG_BY_WIKI_PATH = {
    'alliance/Academy/Faction_Warfare_Plexing': 'faction-warfare-plexing',
    'alliance/Academy/new-player-fleet-guide': 'new-player-fleet-guide',
    'guides/Abyss': 'abyssals',
    'guides/Alesis-Overview-Guide': 'overview-guide',
    'alliance/Academy/faction-warfare-advantage': 'faction-warfare-advantage',
    'guides/Mumble-Setup': 'mumble-setup',
    'guides/pochven-standings': 'pochven-standings',
    'alliance/Academy/Bookmarks': 'bookmarks',
    'guides/battlefields': 'battlefields',
    'guides/zohar-hunting': 'zohar-hunting',
    'guides/rendezvous-wolf': 'rendezvous-wolf',
    'guides/level5s': 'level5-missions',
}

const CATEGORY_ORDER = ['Faction Warfare', 'PVP', 'PVE', 'Utility']

function wikiPathFromHref(href) {
    if (!href) return null
    const cleaned = href.replace(/^https?:\/\/wiki\.minmatar\.org(\/en)?/, '').replace(/^\//, '')
    return cleaned.replace(/\/$/, '') || null
}

function localGuideHref(href) {
    const wikiPath = wikiPathFromHref(href)
    if (!wikiPath) return href
    const slug = SLUG_BY_WIKI_PATH[wikiPath]
    if (slug) return `/guides/${slug}/`
    if (wikiPath === 'guides') return '/guides/'
    return href.startsWith('http') ? href : `${WIKI_BASE}${href.startsWith('/') ? '' : '/'}${href}`
}

function absolutizeAssetSrc(src) {
    if (!src) return src
    if (src.startsWith('http')) return src
    return `${WIKI_BASE}${src.startsWith('/') ? '' : '/'}${src}`
}

function cleanHtml(html) {
    const $ = cheerio.load(html, { decodeEntities: false })

    $('.toc-anchor').remove()
    $('h1, h2, h3, h4, h5, h6').each((_, el) => {
        const $el = $(el)
        $el.removeAttr('id').removeClass('toc-header')
    })

    $('a').each((_, el) => {
        const $el = $(el)
        const href = $el.attr('href')
        if (!href || href.startsWith('#')) {
            $el.replaceWith($el.html() ?? '')
            return
        }
        $el.attr('href', localGuideHref(href))
        $el.removeClass('is-internal-link is-valid-page is-external-link')
    })

    $('img').each((_, el) => {
        const $el = $(el)
        $el.attr('src', absolutizeAssetSrc($el.attr('src')))
        $el.attr('loading', 'lazy')
        $el.removeAttr('width').removeAttr('height')
    })

    $('.table-container').each((_, el) => {
        $(el).replaceWith($(el).html() ?? '')
    })

    return $.root().children().first().html() ?? ''
}

function htmlToMarkdown(html) {
    const $ = cheerio.load(`<div>${html}</div>`, { decodeEntities: false })
    const root = $('div').first()

    function inline($el) {
        let out = ''
        $el.contents().each((_, node) => {
            if (node.type === 'text') {
                out += (node.data ?? '').replace(/\s+/g, ' ')
                return
            }
            if (node.type !== 'tag') return
            const $node = $(node)
            const tag = node.tagName?.toLowerCase()
            const inner = inline($node)
            switch (tag) {
                case 'strong':
                case 'b':
                    out += `**${inner.trim()}**`
                    break
                case 'em':
                case 'i':
                    out += `*${inner.trim()}*`
                    break
                case 'code':
                    out += `\`${inner}\``
                    break
                case 'a': {
                    const href = $node.attr('href') ?? ''
                    out += `[${inner.trim()}](${href})`
                    break
                }
                case 'br':
                    out += '\n'
                    break
                case 'img': {
                    const src = $node.attr('src') ?? ''
                    const alt = $node.attr('alt') ?? ''
                    out += `![${alt}](${src})`
                    break
                }
                case 'span':
                    out += inner
                    break
                default:
                    out += inner
            }
        })
        return out
    }

    function block($el) {
        let out = ''
        $el.contents().each((_, node) => {
            if (node.type === 'text') {
                const text = (node.data ?? '').trim()
                if (text) out += `${text}\n\n`
                return
            }
            if (node.type !== 'tag') return
            const $node = $(node)
            const tag = node.tagName?.toLowerCase()

            switch (tag) {
                case 'h1':
                    out += `# ${inline($node).trim()}\n\n`
                    break
                case 'h2':
                    out += `## ${inline($node).trim()}\n\n`
                    break
                case 'h3':
                    out += `### ${inline($node).trim()}\n\n`
                    break
                case 'h4':
                    out += `#### ${inline($node).trim()}\n\n`
                    break
                case 'h5':
                    out += `##### ${inline($node).trim()}\n\n`
                    break
                case 'h6':
                    out += `###### ${inline($node).trim()}\n\n`
                    break
                case 'p':
                    out += `${inline($node).trim()}\n\n`
                    break
                case 'ul':
                case 'ol': {
                    const ordered = tag === 'ol'
                    let i = 1
                    $node.children('li').each((_, li) => {
                        const prefix = ordered ? `${i}. ` : '- '
                        out += `${prefix}${inline($(li)).trim().replace(/\n/g, '\n  ')}\n`
                        i++
                    })
                    out += '\n'
                    break
                }
                case 'blockquote':
                    inline($node).trim().split('\n').forEach((line) => {
                        if (line.trim()) out += `> ${line.trim()}\n`
                    })
                    out += '\n'
                    break
                case 'table':
                    out += tableToMarkdown($node)
                    out += '\n'
                    break
                case 'div':
                    out += block($node)
                    break
                case 'img':
                    out += `![${$node.attr('alt') ?? ''}](${$node.attr('src') ?? ''})\n\n`
                    break
                default:
                    out += block($node)
            }
        })
        return out
    }

    return block(root).replace(/\n{3,}/g, '\n\n').trim()
}

function tableToMarkdown($table) {
    const rows = []
    $table.find('tr').each((_, tr) => {
        const cells = []
        cheerio.load(tr)('th, td').each((__, cell) => {
            cells.push(cheerio.load(cell).text().replace(/\|/g, '\\|').replace(/\s+/g, ' ').trim())
        })
        if (cells.length) rows.push(cells)
    })
    if (!rows.length) return ''

    const header = rows[0]
    const separator = header.map(() => '---')
    const body = rows.slice(1)
    const lines = [
        `| ${header.join(' | ')} |`,
        `| ${separator.join(' | ')} |`,
        ...body.map((row) => `| ${row.join(' | ')} |`),
    ]
    return `${lines.join('\n')}\n`
}

function yamlEscape(value) {
    if (!value) return "''"
    if (/[:#\n'"&*!?|>[\]{}]/.test(value) || value.startsWith(' ') || value.endsWith(' ')) {
        return `>${value.includes('\n') ? '\n  ' : ' '}${value.replace(/\n/g, '\n  ')}`
    }
    return `'${value.replace(/'/g, "''")}'`
}

function buildSummary(guide) {
    if (guide.description?.trim()) return guide.description.trim()
    const summary = guide.summary?.replace(/^¶\s*/, '').trim() ?? ''
    if (summary.length <= 200) return summary
    return `${summary.slice(0, 197).trim()}...`
}

mkdirSync(guidesDir, { recursive: true })

const exportData = JSON.parse(readFileSync(exportPath, 'utf8'))
const manifest = []

for (const guide of exportData.guides) {
    const slug = SLUG_BY_WIKI_PATH[guide.slug]
    if (!slug) {
        console.warn(`No slug mapping for ${guide.slug}`)
        continue
    }

    const cleanedHtml = cleanHtml(guide.content)
    const markdown = htmlToMarkdown(cleanedHtml)
    const summary = buildSummary(guide)
    const title = guide.index_title || guide.title
    const tags = [...new Set([...(guide.tags ?? []), ...(guide.categories ?? [])])]
        .filter((t) => t !== guide.category)

    const frontmatter = [
        '---',
        `title: ${yamlEscape(title)}`,
        `excerpt: ${yamlEscape(summary)}`,
        `category: ${yamlEscape(guide.category)}`,
        `wiki_url: ${yamlEscape(guide.url)}`,
        tags.length ? `tags: [${tags.map((t) => `'${t.replace(/'/g, "''")}'`).join(', ')}]` : 'tags: []',
        '---',
        '',
    ].join('\n')

    const filePath = join(guidesDir, `${slug}.md`)
    writeFileSync(filePath, `${frontmatter}${markdown}\n`, 'utf8')

    manifest.push({
        slug,
        title,
        excerpt: summary,
        category: guide.category,
        wiki_url: guide.url,
        tags,
        sort_order: CATEGORY_ORDER.indexOf(guide.category),
    })

    console.log(`Wrote ${slug}.md (${markdown.length} chars)`)
}

manifest.sort((a, b) => {
    const cat = a.sort_order - b.sort_order
    if (cat !== 0) return cat
    return a.title.localeCompare(b.title)
})

const indexTs = `import type { GuideMeta } from '@/data/guides/types'

${manifest.map((g) => `import ${g.slug.replace(/-/g, '_')} from '@markdown/guides/${g.slug}.md'`).join('\n')}

type GuideModule = {
    frontmatter: {
        title: string
        excerpt: string
        category: string
        wiki_url: string
        tags: string[]
    }
    rawContent: () => string
}

const guideModules: Record<string, GuideModule> = {
${manifest.map((g) => `    '${g.slug}': ${g.slug.replace(/-/g, '_')},`).join('\n')}
}

export const guideCategories = ${JSON.stringify(CATEGORY_ORDER)} as const

export const guides: GuideMeta[] = ${JSON.stringify(manifest.map(({ sort_order, ...rest }) => rest), null, 4)}

export function getGuideBySlug(slug: string): (GuideMeta & { module: GuideModule }) | undefined {
    const meta = guides.find((guide) => guide.slug === slug)
    const module = guideModules[slug]
    if (!meta || !module) return undefined
    return { ...meta, module }
}

export function getGuidesByCategory(): Record<string, GuideMeta[]> {
    const grouped: Record<string, GuideMeta[]> = {}
    for (const category of guideCategories) {
        grouped[category] = guides.filter((guide) => guide.category === category)
    }
    return grouped
}
`

mkdirSync(join(repoRoot, 'frontend/app/src/data/guides'), { recursive: true })

writeFileSync(join(repoRoot, 'frontend/app/src/data/guides/types.ts'), `export type GuideMeta = {
    slug: string
    title: string
    excerpt: string
    category: string
    wiki_url: string
    tags: string[]
}
`, 'utf8')

writeFileSync(join(repoRoot, 'frontend/app/src/data/guides/index.ts'), indexTs, 'utf8')
console.log(`\nGenerated ${manifest.length} guides`)
