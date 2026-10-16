// Wraps the native helper (src/native/helper.cs): which window is in front, where the EVE clients
// are, and the glass effect and window order for our own windows. Read-only towards EVE: no injection,
// no memory reading, no input. Windows only; elsewhere the app runs without overlay awareness or glass.
const { spawn } = require('child_process')
const { EventEmitter } = require('events')
const fs = require('fs')
const path = require('path')

const GLASS_TINT = '40080808'   // AABBGGRR: light native tint; the window's CSS adds the rest to match EVE's transparency setting

class EveClients extends EventEmitter {
    constructor({ user_data_dir, client_procs }) {
        super()
        this.user_data_dir = user_data_dir
        this.client_procs = client_procs
        this.proc = null
        this.ready = false
        this.failed = false   // helper exited before it was ready: run without overlay awareness
        this.foreground = { client: false, pid: 0, hwnd: '0', proc: '', cls: '' }
        this.clients = []
    }

    get supported() {
        return process.platform === 'win32'
    }

    get eve_running() {
        return this.clients.length > 0
    }

    start() {
        if (!this.supported || this.proc) return
        // Source ships inside the app (asar); PowerShell compiles it with Add-Type at launch.
        const source = fs.readFileSync(path.join(__dirname, '..', 'native', 'helper.cs'), 'utf8').replace(/\r?\n/g, '\r\n')
        const script = path.join(this.user_data_dir, 'eve-helper.ps1')
        fs.mkdirSync(this.user_data_dir, { recursive: true })
        fs.writeFileSync(script, `﻿$src = @'\r\n${source}\r\n'@\r\nAdd-Type -TypeDefinition $src -Language CSharp\r\n[MfoHelper]::Run($args[0])\r\n`, 'utf8')

        this.proc = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', script, this.client_procs],
            { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] })
        let buffer = ''
        this.proc.stdout.on('data', chunk => {
            buffer += chunk
            let i
            while ((i = buffer.indexOf('\n')) >= 0) {
                const line = buffer.slice(0, i).trim()
                buffer = buffer.slice(i + 1)
                if (line) this.on_line(line)
            }
        })
        this.proc.stderr.on('data', d => this.emit('log', { t: 'helper-stderr', text: String(d).slice(0, 400) }))
        this.proc.on('error', err => {   // PowerShell missing or blocked
            this.proc = null
            this.failed = true
            this.emit('log', { t: 'helper-error', message: err.message })
            this.emit('change')
        })
        // A helper that never reports in must not keep the overlay hidden forever.
        this.ready_timer = setTimeout(() => {
            if (this.ready) return
            this.failed = true
            this.emit('log', { t: 'helper-timeout' })
            this.emit('change')
        }, 8000)
        this.proc.on('exit', code => {
            this.proc = null
            if (!this.ready) this.failed = true
            this.ready = false
            this.emit('log', { t: 'helper-exit', code })
            this.emit('change')
        })
    }

    stop() {
        clearTimeout(this.ready_timer)
        if (!this.proc) return
        this.send('quit')
        this.proc.kill()
        this.proc = null
    }

    send(line) {
        try { this.proc && this.proc.stdin.write(line + '\n') } catch (e) {}
    }

    on_line(line) {
        let message
        try { message = JSON.parse(line) } catch (e) { return }
        if (message.t === 'ready') {
            clearTimeout(this.ready_timer)
            this.ready = true
            this.failed = false
            this.emit('ready')
        } else if (message.t === 'fg') {
            this.foreground = { client: message.client, pid: message.pid, hwnd: message.hwnd, title: message.title, proc: message.proc || '', cls: message.cls || '' }
            this.emit('change')
            if (message.client) this.emit('client-front')
        } else if (message.t === 'clients') {
            this.clients = message.list
            // Logging in renames the window ("EVE" -> "EVE - <Character>") without a focus change,
            // so refresh the foreground title from the client list.
            const front = this.clients.find(c => c.hwnd === this.foreground.hwnd)
            if (front) this.foreground = { ...this.foreground, title: front.title }
            this.emit('change')
        } else {
            this.emit('log', message)
        }
    }

    apply_glass(win) {
        if (!this.proc || win.isDestroyed()) return
        this.send(`glass ${hwnd_of(win)} ${GLASS_TINT}`)
    }

    // "Stay with EVE": put our windows directly above an EVE client in the window order, without activating them.
    stack(client_hwnd, wins) {
        if (!this.proc || !this.ready) return
        const hwnds = wins.filter(w => w && !w.isDestroyed()).map(hwnd_of)
        if (hwnds.length) this.send(`stack ${client_hwnd} ${hwnds.join(' ')}`)
    }
}

function hwnd_of(win) {
    const handle = win.getNativeWindowHandle()
    return (handle.length >= 8 ? handle.readBigUInt64LE(0) : BigInt(handle.readUInt32LE(0))).toString()
}

module.exports = { EveClients }
