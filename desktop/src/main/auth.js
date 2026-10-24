// Discord login, the same way the website does it.
//
// The backend's GET /api/users/login?redirect_url=<url> sends the browser to Discord, then its
// /api/users/callback redirects to <url>?token=<JWT> (or ?error=<code>&id=<id>). The website uses
// https://my.minmatar.org/auth/login as <url>; the desktop app uses a one-shot loopback listener
// (RFC 8252 "loopback redirect") so the token lands in this process, not in a web page.
//
// The callback path carries a random nonce so nothing else on the machine can feed us a token.
const http = require('http')
const crypto = require('crypto')
const fs = require('fs')
const path = require('path')

const LOGIN_TIMEOUT_MS = 5 * 60_000

function build_login_url(api_url, redirect_url) {
    return `${api_url}/api/users/login?redirect_url=${encodeURIComponent(redirect_url)}`
}

function result_page(ok, message) {
    const title = ok ? 'Signed in to Minmatar Fleet' : 'Sign-in failed'
    return `<!doctype html><html><head><meta charset="utf-8"><title>${title}</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0b0b0b;color:#d6d6d6;font:15px "Segoe UI",sans-serif}
main{padding:28px 32px;border:1px solid rgba(255,255,255,.08);border-top:1px solid #b53620;background:#141414;max-width:420px}
h1{margin:0 0 8px;font-size:18px;font-weight:500;color:${ok ? '#fff' : '#e0362a'}}p{margin:0;color:#8c8c8c}</style></head>
<body><main><h1>${title}</h1><p>${message}</p></main></body></html>`
}

class LoginCancelled extends Error {}
class LoginFailed extends Error {
    constructor(code, id) {
        super(`Discord login failed: ${code}${id ? ` (${id})` : ''}`)
        this.code = code
        this.error_id = id
    }
}

// Starts the loopback listener, opens the browser, resolves with the JWT.
// open_external is injected (Electron's shell.openExternal) so this is testable without Electron.
function start_login({ api_url, open_external, timeout_ms = LOGIN_TIMEOUT_MS }) {
    const nonce = crypto.randomBytes(16).toString('hex')
    const callback_path = `/callback/${nonce}`
    let server
    let timer
    let settle

    const promise = new Promise((resolve, reject) => {
        settle = (err, token) => {
            clearTimeout(timer)
            if (server) server.close()
            server = null
            err ? reject(err) : resolve(token)
        }

        server = http.createServer((req, res) => {
            const url = new URL(req.url, 'http://127.0.0.1')
            if (url.pathname !== callback_path) {
                res.writeHead(404).end()
                return
            }
            const token = url.searchParams.get('token')
            const error = url.searchParams.get('error')
            res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' })
            if (token) {
                res.end(result_page(true, 'You can close this tab and return to the Minmatar Fleet app.'))
                settle(null, token)
            } else {
                const code = error || 'NO_TOKEN'
                res.end(result_page(false, `Discord login did not complete (${code}). Close this tab and try again from the app.`))
                settle(new LoginFailed(code, url.searchParams.get('id')))
            }
        })

        server.on('error', err => settle(err))
        server.listen(0, '127.0.0.1', async () => {
            const { port } = server.address()
            const redirect_url = `http://127.0.0.1:${port}${callback_path}`
            timer = setTimeout(() => settle(new LoginCancelled('Timed out waiting for Discord login')), timeout_ms)
            try {
                await open_external(build_login_url(api_url, redirect_url))
            } catch (err) {
                settle(err)
            }
        })
    })

    return {
        promise,
        cancel: () => settle && settle(new LoginCancelled('Login cancelled')),
    }
}

// Reads the (unverified) JWT payload for display only. The backend verifies the signature on every call.
function decode_token_payload(token) {
    try {
        const part = token.split('.')[1]
        return JSON.parse(Buffer.from(part.replace(/-/g, '+').replace(/_/g, '/'), 'base64').toString('utf8'))
    } catch (e) {
        return null
    }
}

// Token at rest is encrypted with Electron safeStorage (DPAPI on Windows, Keychain on macOS,
// libsecret on Linux). If encryption is unavailable the token is kept in memory only.
class TokenStore {
    constructor(file, safe_storage) {
        this.file = file
        this.safe_storage = safe_storage
        this.memory = null
    }

    can_persist() {
        return !!(this.safe_storage && this.safe_storage.isEncryptionAvailable())
    }

    save(token) {
        this.memory = token
        if (!this.can_persist()) return false
        fs.mkdirSync(path.dirname(this.file), { recursive: true })
        fs.writeFileSync(this.file, this.safe_storage.encryptString(token))
        return true
    }

    load() {
        if (this.memory) return this.memory
        if (!this.can_persist() || !fs.existsSync(this.file)) return null
        try {
            this.memory = this.safe_storage.decryptString(fs.readFileSync(this.file))
        } catch (e) {
            this.memory = null
        }
        return this.memory
    }

    clear() {
        this.memory = null
        try { fs.unlinkSync(this.file) } catch (e) {}
    }
}

module.exports = { start_login, build_login_url, decode_token_payload, TokenStore, LoginCancelled, LoginFailed }
