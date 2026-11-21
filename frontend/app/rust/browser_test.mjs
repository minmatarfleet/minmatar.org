// Runs every Rust story in a real browser against a running Rust server
// (`npm run rust:serve`, or the dev server): each story must render without a
// page error and its play() test must pass, with Alpine, htmx and tippy loaded
// as on the site. Accessibility (axe) results are reported per story.
//
//   node rust/browser_test.mjs [base_url] [--a11y-strict] [--filter=forms/]
//
// base_url defaults to http://127.0.0.1:6007/rust/. Exits 1 on any failure.
import { chromium } from 'playwright'

const args = process.argv.slice(2)
const base_url = (args.find((arg) => !arg.startsWith('--')) ?? 'http://127.0.0.1:6007/rust/').replace(/\/?$/, '/')
const a11y_strict = args.includes('--a11y-strict')
const filter = args.find((arg) => arg.startsWith('--filter='))?.slice('--filter='.length)
const STORY_TIMEOUT = 20_000
const WORKERS = Number(process.env.RUST_BROWSER_WORKERS ?? 4)

const index = await (await fetch(new URL('index.json', base_url))).json()
const stories = Object.values(index.entries)
    .filter((entry) => entry.type === 'story')
    .filter((entry) => !filter || entry.importPath.includes(filter) || entry.id.includes(filter))

if (stories.length === 0) {
    console.error(`No stories at ${base_url}index.json`)
    process.exit(1)
}

const browser = await chromium.launch()
const results = []

async function run_worker(queue) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
    let page_errors = []
    page.on('pageerror', (error) => page_errors.push(error.message))

    await page.goto(`${base_url}iframe.html`, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction(() => window.__STORYBOOK_ADDONS_CHANNEL__ && window.__STORYBOOK_PREVIEW__, null, { timeout: 60_000 })

    for (let story = queue.shift(); story; story = queue.shift()) {
        page_errors = []
        let outcome
        try {
            outcome = await page.evaluate(({ id, timeout }) => new Promise((resolve) => {
                const channel = window.__STORYBOOK_ADDONS_CHANNEL__
                const listeners = {}
                const finish = (result) => {
                    for (const [event, listener] of Object.entries(listeners))
                        channel.off(event, listener)
                    clearTimeout(timer)
                    resolve(result)
                }
                const on = (event, listener) => {
                    listeners[event] = listener
                    channel.on(event, listener)
                }
                const timer = setTimeout(() => finish({ status: 'timeout' }), timeout)

                on('storyErrored', (error) => finish({ status: 'error', message: `${error?.title ?? ''} ${error?.description ?? ''}`.trim() }))
                on('storyThrewException', (error) => finish({ status: 'error', message: error?.message ?? String(error) }))
                on('playFunctionThrewException', (error) => finish({ status: 'play', message: error?.message ?? String(error) }))
                on('storyMissing', () => finish({ status: 'error', message: 'story missing' }))
                on('storyFinished', (event) => {
                    if (event?.storyId !== id)
                        return
                    const a11y = (event.reporters ?? []).find((report) => report.type === 'a11y')
                    const violations = (a11y?.result?.violations ?? []).map((violation) => ({
                        id: violation.id,
                        impact: violation.impact,
                        nodes: violation.nodes?.length ?? 0,
                    }))
                    finish({
                        status: event.status === 'error' ? 'play' : 'ok',
                        message: event.status === 'error' ? 'story finished with errors' : undefined,
                        violations,
                    })
                })

                channel.emit('setCurrentStory', { storyId: id, viewMode: 'story' })
            }), { id: story.id, timeout: STORY_TIMEOUT })
        } catch (error) {
            outcome = { status: 'error', message: error.message }
        }

        // An uncaught error in the story's own scripts fails it too.
        if (outcome.status === 'ok' && page_errors.length)
            outcome = { ...outcome, status: 'error', message: page_errors.join(' | ') }

        results.push({ story, ...outcome })
        const mark = outcome.status === 'ok' ? '✓' : '✗'
        const a11y = outcome.violations?.length ? `  (a11y: ${outcome.violations.map((v) => v.id).join(', ')})` : ''
        console.log(`${mark} ${story.title} › ${story.name}${outcome.message ? ` — ${outcome.message}` : ''}${a11y}`)
    }
    await page.close()
}

const queue = [...stories]
await Promise.all(Array.from({ length: Math.min(WORKERS, stories.length) }, () => run_worker(queue)))
await browser.close()

const failed = results.filter((result) => result.status !== 'ok')
const with_violations = results.filter((result) => result.violations?.length)
const rule_counts = {}
for (const result of with_violations)
    for (const violation of result.violations)
        rule_counts[violation.id] = (rule_counts[violation.id] ?? 0) + 1

console.log(`\n${results.length - failed.length}/${results.length} stories passed in the browser.`)
if (with_violations.length) {
    console.log(`${with_violations.length} stories have accessibility violations:`)
    for (const [rule, count] of Object.entries(rule_counts).sort((a, b) => b[1] - a[1]))
        console.log(`  ${rule}: ${count}`)
}

process.exit(failed.length || (a11y_strict && with_violations.length) ? 1 : 0)
