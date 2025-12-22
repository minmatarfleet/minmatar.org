/** @type {import('tailwindcss').Config} */
import animations from '@midudev/tailwind-animations'
import typography from '@tailwindcss/typography'

export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      typography: {
        DEFAULT: {
          css: {
            color: 'var(--fleet-yellow)',
            a: {
              color: 'var(--highlight)',
            },
            h1: {
              fontWeight: '500',
              color: 'var(--highlight)',
            },
            h2: {
              fontWeight: '500',
              color: 'var(--highlight)',
            },
            h3: {
              fontWeight: '500',
              color: 'var(--highlight)',
            },
            h4: {
              fontWeight: '600',
              color: 'var(--highlight)',
            },
            h5: {
              fontWeight: '600',
              color: 'var(--highlight)',
            },
            h6: {
              fontWeight: '600',
              color: 'var(--highlight)',
            },
            ul: {
              listStyleType: 'square',
            },
            strong: {
              fontWeight: '600',
              color: 'inherit',
            },
            b: {
              fontWeight: '600',
              color: 'inherit',
            },
            pre: {
              border: 'solid 1px var(--border-color)',
              backgroundColor: 'var(--background)',
              borderRadius: '0',
            },
            code: {
              fontWeight: 'inherit',
              color: 'var(--highlight)',
              border: 'solid 1px var(--border-color)',
              borderRadius: '0',
            },
            blockquote: {
              color: 'var(--highlight)',
              borderInlineStartStyle: 'solid',
              borderInlineStartColor: 'var(--highlight)',
              paddingTop: '1px',
              paddingBottom: '1px',
            },
            th: {
              color: 'var(--highlight)',
            }
          },
        },
      },
    },
  },
  plugins: [ animations, typography ],
}