// Each window loads several classic <script>s that share one global scope. A second top-level
// `function render_fleet` in any of them silently replaces the first (v0.10.0 blanked the Upcoming list
// that way). Compiling a page's scripts together inside one strict block turns any duplicate top-level
// function, let, const or class into an early SyntaxError, so the collision fails here instead.
const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const vm = require('vm')

const RENDERER = path.join(__dirname, '..', 'src', 'renderer')

// Local scripts in load order (no remote scripts: the windows' CSP is script-src 'self').
function page_scripts(html) {
    return [...html.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*>/g)].map(m => m[1])
}

// The globals the shared modules publish (`root.fleet_view = api`). A page script declaring one of these
// names would shadow the module, so they count as declared too.
function published_globals(source) {
    return [...source.matchAll(/\broot\.([A-Za-z_$][\w$]*)\s*=/g)].map(m => m[1])
}

// Returns null when the page's scripts can share one scope, else the compile error.
function scope_error(scripts) {
    const published = [...new Set(scripts.flatMap(s => published_globals(s.source)))]
    const header = published.length ? `let ${published.join(', ')};\n` : ''
    const body = scripts.map(s => `// ---- ${s.name}\n${s.source}\n`).join('')
    try {
        new vm.Script(`'use strict';{\n${header}${body}}`, { filename: scripts.map(s => s.name).join('+') })
        return null
    } catch (err) {
        return err
    }
}

const pages = fs.readdirSync(RENDERER).filter(name => name.endsWith('.html'))

test('every window page loads at least one script', () => {
    assert.ok(pages.length >= 6)
    for (const page of pages) assert.ok(page_scripts(fs.readFileSync(path.join(RENDERER, page), 'utf8')).length, page)
})

for (const page of pages) {
    test(`${page}: its scripts declare no top-level name twice`, () => {
        const names = page_scripts(fs.readFileSync(path.join(RENDERER, page), 'utf8'))
        const scripts = names.map(name => ({ name, source: fs.readFileSync(path.join(RENDERER, name), 'utf8') }))
        const err = scope_error(scripts)
        assert.equal(err, null, err && `${page}: ${err.message}`)
    })
}

test('catches the render_fleet collision and cross-file clashes', () => {
    const one = { name: 'a.js', source: 'function render_fleet() { return 1 }\nfunction render_fleet() { return 2 }' }
    assert.match(scope_error([one]).message, /render_fleet/)
    const a = { name: 'a.js', source: 'const esc = v => v' }
    const b = { name: 'b.js', source: 'function esc(v) { return v }' }
    assert.match(scope_error([a, b]).message, /esc/)
    const module = { name: 'm.js', source: '(function (root) { root.fleet_view = {} })(this)' }
    const page = { name: 'p.js', source: 'const fleet_view = window.fleet_view' }
    assert.match(scope_error([module, page]).message, /fleet_view/)
    assert.equal(scope_error([module, { name: 'p.js', source: 'const view = window.fleet_view' }]), null)
})
