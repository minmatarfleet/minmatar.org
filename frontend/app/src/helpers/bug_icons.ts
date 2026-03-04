const icons = [
    '/images/bug_icons/kekw.png'
]

const get_random_icon = () => {
    return icons[Math.floor(Math.random() * icons.length)];
}

import { icons_bug, icons_bug_percentage } from '@helpers/env';

const FEATURE_ACTIVE = icons_bug()
const BUG_PERCENTAGE = icons_bug_percentage()

export const get_bug_icon = (icon:string) => {
    return FEATURE_ACTIVE && Math.random() <= BUG_PERCENTAGE ? get_random_icon() : icon
}