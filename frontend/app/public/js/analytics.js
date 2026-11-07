// Product analytics events. PostHog only loads in production builds
// (components/partials/Posthog.astro), so in dev and tests this is a no-op.
// A failed capture must never break the action it measures.
window.capture_event = function (name, properties, options) {
    try {
        if (window.posthog && typeof window.posthog.capture === 'function')
            window.posthog.capture(name, properties || {}, options)
    } catch (e) {}
}
