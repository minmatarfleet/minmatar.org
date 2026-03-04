export const icons = [
    '/images/bug_icons/kekw.png'
]

export const get_random_icon = () => {
    return icons[Math.floor(Math.random() * icons.length)];
}