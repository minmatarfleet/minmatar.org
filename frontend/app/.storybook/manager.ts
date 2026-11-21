import { addons } from 'storybook/manager-api'
import { rust_theme } from './theme'

addons.setConfig({
    theme: rust_theme,
    sidebar: {
        showRoots: true,
    },
})
