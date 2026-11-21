import { create } from 'storybook/theming'

// Site tokens (src/styles/properties/_colors.scss) as literal values: the
// Storybook manager is not styled by the site's CSS.
export const rust_theme = create({
    base: 'dark',
    brandTitle: 'Rust · Minmatar Fleet components',
    brandUrl: 'https://my.minmatar.org/brand/',
    brandImage: 'https://my.minmatar.org/images/fleet-logo.png',
    brandTarget: '_self',

    colorPrimary: '#b53620',
    colorSecondary: '#b53620',

    appBg: '#121212',
    appContentBg: '#191919',
    appPreviewBg: '#121212',
    appBorderColor: 'rgba(255, 255, 255, 0.08)',
    appBorderRadius: 0,

    fontBase: '"Montserrat Variable", "Montserrat", sans-serif',

    textColor: '#f1d9a0',
    textInverseColor: '#121212',
    textMutedColor: 'rgba(255, 255, 255, 0.55)',

    barTextColor: 'rgba(255, 255, 255, 0.55)',
    barSelectedColor: '#f1d9a0',
    barHoverColor: '#f1d9a0',
    barBg: '#191919',

    inputBg: '#121212',
    inputBorder: 'rgba(255, 255, 255, 0.12)',
    inputTextColor: '#f1d9a0',
    inputBorderRadius: 0,
})
