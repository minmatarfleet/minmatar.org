const { test } = require('node:test')
const assert = require('node:assert/strict')
const { parse, compare, check_pr } = require('../scripts/check_version')

test('semver parsing and ordering', () => {
    assert.deepEqual(parse('1.2.3'), { major: 1, minor: 2, patch: 3, pre: null })
    assert.equal(parse('1.2'), null)
    assert.equal(parse('01.2.3'), null)
    assert.equal(compare('0.4.0', '0.3.9'), 1)
    assert.equal(compare('0.10.0', '0.9.0'), 1)
    assert.equal(compare('1.0.0-beta.1', '1.0.0'), -1)
    assert.equal(compare('1.0.0', '1.0.0'), 0)
})

const released = ['v0.4.0']

test('bumped version on a PR: ok, and says merging will release it', () => {
    const r = check_pr({ version: '0.4.1', base_version: '0.4.0', released, changed: true })
    assert.equal(r.ok, true)
    assert.match(r.messages[0], /Merging will release desktop v0\.4\.1/)
})

test('changed app without a bump: ok, notice that nothing will be released', () => {
    const r = check_pr({ version: '0.4.0', base_version: '0.4.0', released, changed: true })
    assert.equal(r.ok, true)
    assert.match(r.messages[0], /will not publish a release/)
})

test('fails on non-semver, going backwards, or reusing a released version', () => {
    assert.equal(check_pr({ version: '0.5', base_version: '0.4.0', released, changed: true }).ok, false)
    assert.equal(check_pr({ version: '0.3.9', base_version: '0.4.0', released, changed: true }).ok, false)
    assert.equal(check_pr({ version: '0.4.0', base_version: '0.3.3', released, changed: true }).ok, false)
})

test('first release (nothing released, nothing on main yet)', () => {
    assert.equal(check_pr({ version: '0.4.0', base_version: '', released: [], changed: true }).ok, true)
})
