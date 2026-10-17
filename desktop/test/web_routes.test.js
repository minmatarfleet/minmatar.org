const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const path = require('path')
const routes = require('../src/main/web_routes')

test('website routes use the configured base', () => {
    const base = 'http://localhost:4321'
    assert.equal(routes.fleet(base, 7), 'http://localhost:4321/fleets/upcoming/7')
    assert.equal(routes.fleet(base, '7', { ended: true }), 'http://localhost:4321/fleets/history/7')
    assert.equal(routes.srp_killmails(base), 'http://localhost:4321/ships/srp/killmails/')
    assert.equal(routes.campaign(base, 'a b/c'), 'http://localhost:4321/campaigns/a%20b%2Fc')
    assert.equal(routes.intel_scan(base, 'r/1'), 'http://localhost:4321/intel/scans/r%2F1')
})

// backend/app/tests/test_web_links.py checks the website still serves each of these pages.
test('only web_routes.js builds website paths in the main process', () => {
    const dir = path.join(__dirname, '../src/main')
    const offenders = []
    for (const file of fs.readdirSync(dir).filter(f => f.endsWith('.js') && f !== 'web_routes.js')) {
        const source = fs.readFileSync(path.join(dir, file), 'utf8')
        if (/\$\{(this\.)?web_url\}\//.test(source)) offenders.push(file)
        if (/['"`]https:\/\/my\.minmatar\.org\//.test(source)) offenders.push(file)
    }
    assert.deepEqual(offenders, [])
})
