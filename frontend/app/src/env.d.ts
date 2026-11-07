/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />

interface Window {
    capture_event?: (name: string, properties?: Record<string, unknown>, options?: Record<string, unknown>) => void
}