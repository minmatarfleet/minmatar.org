// Container healthcheck for the rust service (docker-compose-prod.yml).
// Same drain rule as frontend/healthcheck.mjs: scripts/deploy.sh touches
// /tmp/drain before stopping an old container so edge stops routing to it.
// /rust/health only answers 200 once a real component has rendered.
import fs from 'node:fs'
import http from 'node:http'

const PORT = Number(process.env.PORT ?? 6007)

if (fs.existsSync('/tmp/drain'))
    process.exit(1)

const request = http.request({ host: '127.0.0.1', port: PORT, path: '/rust/health', method: 'GET', timeout: 4000 }, (response) => {
    process.exit(response.statusCode === 200 ? 0 : 1)
})
request.on('timeout', () => process.exit(1))
request.on('error', () => process.exit(1))
request.end()
