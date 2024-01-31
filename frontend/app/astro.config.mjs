import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';
// import alpine from '@astrojs/alpinejs';
// import svelte from '@astrojs/svelte';
import node from '@astrojs/node';

// https://astro.build/config
export default defineConfig({
    output: 'server',
    adapter: node({
        mode: 'standalone'
    }),
    prefetch: {
        defaultStrategy: 'viewport'
    },
    integrations: [
        tailwind({
            applyBaseStyles: false,
        }),
        // alpine(),
        // svelte()
    ],
});
