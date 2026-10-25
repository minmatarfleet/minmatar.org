// Container healthcheck for zero-downtime deploys (scripts/deploy.sh); same
// rules as backend/healthcheck.py. /tmp/drain fails the check so Traefik stops
// routing here before the old container is stopped; the first success needs
// an HTTP response, later ones only the listening socket.
import fs from 'node:fs'
import http from 'node:http'
import net from 'node:net'

const PORT = 4321
const DRAIN_FILE = '/tmp/drain'
const READY_FILE = '/tmp/ready'

const fail = () => process.exit(1)

if (fs.existsSync(DRAIN_FILE)) fail()

if (fs.existsSync(READY_FILE)) {
    const socket = net.connect(PORT, '127.0.0.1', () => {
        socket.end()
        process.exit(0)
    })
    socket.setTimeout(4000, fail)
    socket.on('error', fail)
} else {
    const request = http.request({ host: '127.0.0.1', port: PORT, path: '/favicon.svg', method: 'HEAD', timeout: 4000 }, () => {
        fs.writeFileSync(READY_FILE, '')
        process.exit(0)
    })
    request.on('timeout', fail)
    request.on('error', fail)
    request.end()
}
