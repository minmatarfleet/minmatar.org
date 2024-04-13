import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
import node from '@astrojs/node';
import sentry from "@sentry/astro";
import { loadEnv } from "vite";

const env = loadEnv(import.meta.env.MODE, process.cwd(), "");

const SENTRY_AUTH_TOKEN = env.SENTRY_AUTH_TOKEN ?? false
const SENTRY_DSN = env.SENTRY_DSN ?? 'https://2b2a3278ee0475acd93320373b7c31d6@o4507073814528000.ingest.us.sentry.io/4507074455601152'
const SENTRY_PROJECT = env.SENTRY_PROJECT ?? 'my_minmatar_org'

// https://astro.build/config
export default defineConfig({
    output: 'server',
    adapter: node({
        mode: 'standalone'
    }),
    prefetch: false,
    integrations: [
        tailwind({
            applyBaseStyles: false,
        }),
        SENTRY_AUTH_TOKEN ?
        sentry({
            dsn: SENTRY_DSN,
            sourceMapsUploadOptions: {
                project: SENTRY_PROJECT,
                authToken: SENTRY_AUTH_TOKEN,
            },
        })
        :
        null,
    ],
    vite: {
        server: {
            watch: {
                usePolling: true
            }
        }
    }
});
