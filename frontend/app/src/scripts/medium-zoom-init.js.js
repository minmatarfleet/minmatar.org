import mediumZoom from 'medium-zoom'

export default function initZoom() {
    mediumZoom('.zoomable', {
        margin: 24,
        background: 'rgba(22, 22, 22, 0.85)',
    })
}

if (typeof window !== 'undefined') {
    initZoom()
}