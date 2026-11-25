// Test data for the Features/Voice stories: the /voice setup steps at each point of the flow.
// Typed with the component's own prop type, so `npm run check` fails when it changes.
import type { VoiceProgressStep } from '@dtypes/layout_components'

const LABELS = ['Sign in', 'Access', 'Install', 'Connect', 'Keys']

const steps = (states: VoiceProgressStep['state'][]): VoiceProgressStep[] =>
    LABELS.map((label, index) => ({ label, state: states[index] }))

/** Signed out: the pilot is about to sign in. */
export const voice_steps_sign_in = steps(['now', 'todo', 'todo', 'todo', 'todo'])

/** Signed in and admitted, Mumble not set up yet. */
export const voice_steps_install = steps(['done', 'done', 'now', 'todo', 'todo'])

/** Mumble set up: one click to connect. */
export const voice_steps_connect = steps(['done', 'done', 'done', 'now', 'todo'])
