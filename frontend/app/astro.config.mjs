import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import node from '@astrojs/node';
import sentry from "@sentry/astro";
import { loadEnv } from "vite";

const env = loadEnv(import.meta.env.MODE, process.cwd(), "")

const SENTRY_AUTH_TOKEN = env.SENTRY_AUTH_TOKEN ?? false
const SENTRY_DSN = env.SENTRY_DSN
const SENTRY_PROJECT = env.SENTRY_PROJECT

if (SENTRY_DSN === undefined)
    throw new Error(`Please define enviroment variable SENTRY_DSN`)

if (SENTRY_PROJECT === undefined)
    throw new Error(`Please define enviroment variable SENTRY_PROJECT`)

const integrations = [
    tailwind({
        applyBaseStyles: false,
    })
]

if (SENTRY_AUTH_TOKEN)
    integrations.push(sentry({
        dsn: SENTRY_DSN,
        sourceMapsUploadOptions: {
            project: SENTRY_PROJECT,
            authToken: SENTRY_AUTH_TOKEN,
        },
        _experiments: {
            enableLogs: true,
        },
    }))

// https://astro.build/config
export default defineConfig({
    output: 'server',
    adapter: node({
        mode: 'standalone'
    }),
    security: {
        checkOrigin: false
    },
    devToolbar: { enabled: false },
    prefetch: false,
    integrations: integrations,
    vite: {
        server: {
            watch: {
                usePolling: true
            }
        }
    }
});
