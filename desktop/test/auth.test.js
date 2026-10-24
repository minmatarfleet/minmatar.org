const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const { start_login, build_login_url, decode_token_payload, TokenStore, LoginFailed, LoginCancelled } = require('../src/main/auth')

// Stands in for the browser: follows the backend's final redirect to the loopback callback.
function browser_that_returns(query) {
    return async login_url => {
        const redirect = new URL(login_url).searchParams.get('redirect_url')
        const response = await fetch(`${redirect}?${query}`)
        await response.text()
    }
}

test('login URL uses the backend /api/users/login with an encoded redirect_url', () => {
    assert.equal(
        build_login_url('https://api.minmatar.org', 'http://127.0.0.1:5000/callback/abc'),
        'https://api.minmatar.org/api/users/login?redirect_url=http%3A%2F%2F127.0.0.1%3A5000%2Fcallback%2Fabc',
    )
})

test('loopback redirect is 127.0.0.1 with a random nonce path', async () => {
    let seen
    const flow = start_login({ api_url: 'https://api.example', open_external: async url => { seen = url; flow.cancel() } })
    await assert.rejects(flow.promise, LoginCancelled)
    const redirect = new URL(new URL(seen).searchParams.get('redirect_url'))
    assert.equal(redirect.hostname, '127.0.0.1')
    assert.match(redirect.pathname, /^\/callback\/[0-9a-f]{32}$/)
})

test('resolves with the token from ?token=', async () => {
    const flow = start_login({ api_url: 'https://api.example', open_external: browser_that_returns('token=abc.def.ghi') })
    assert.equal(await flow.promise, 'abc.def.ghi')
})

test('rejects with the backend error code and id', async () => {
    const flow = start_login({ api_url: 'https://api.example', open_external: browser_that_returns('error=DENIED&id=XYZ') })
    await assert.rejects(flow.promise, err => err instanceof LoginFailed && err.code === 'DENIED' && err.error_id === 'XYZ')
})

test('ignores requests to any other path', async () => {
    let redirect
    const flow = start_login({
        api_url: 'https://api.example',
        open_external: async url => {
            redirect = new URL(new URL(url).searchParams.get('redirect_url'))
            const wrong = await fetch(`${redirect.origin}/callback/not-the-nonce?token=evil`)
            assert.equal(wrong.status, 404)
            await (await fetch(`${redirect.href}?token=good`)).text()
        },
    })
    assert.equal(await flow.promise, 'good')
})

test('times out', async () => {
    const flow = start_login({ api_url: 'https://api.example', open_external: async () => {}, timeout_ms: 50 })
    await assert.rejects(flow.promise, LoginCancelled)
})

test('decodes the JWT payload for display', () => {
    const payload = Buffer.from(JSON.stringify({ username: 'kaleb', user_id: 1 })).toString('base64url')
    assert.deepEqual(decode_token_payload(`x.${payload}.y`), { username: 'kaleb', user_id: 1 })
    assert.equal(decode_token_payload('garbage'), null)
})

const fake_safe_storage = (available = true) => ({
    isEncryptionAvailable: () => available,
    encryptString: s => Buffer.from(`enc:${s}`),
    decryptString: b => b.toString().replace(/^enc:/, ''),
})

test('token store encrypts at rest and round-trips', () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'mf-')), 'session.bin')
    const store = new TokenStore(file, fake_safe_storage())
    assert.equal(store.save('tok'), true)
    assert.equal(fs.readFileSync(file, 'utf8'), 'enc:tok')
    assert.equal(new TokenStore(file, fake_safe_storage()).load(), 'tok')
    store.clear()
    assert.equal(fs.existsSync(file), false)
    assert.equal(new TokenStore(file, fake_safe_storage()).load(), null)
})

test('token store keeps the token in memory only when encryption is unavailable', () => {
    const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'mf-')), 'session.bin')
    const store = new TokenStore(file, fake_safe_storage(false))
    assert.equal(store.save('tok'), false)
    assert.equal(store.load(), 'tok')
    assert.equal(fs.existsSync(file), false)
})
