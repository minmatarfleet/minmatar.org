import * as Sentry from '@sentry/astro'

const dsn = import.meta.env.PUBLIC_SENTRY_DSN
const enabled = Boolean(dsn)
	&& !String(dsn).includes('DUMMY')
	&& import.meta.env.PROD

Sentry.init({
	dsn,
	enabled,
	environment: enabled ? 'production' : undefined,
	ignoreErrors: [
		'Transition was aborted because of invalid state',
		'Transition was skipped',
		/AbortError: Transition was skipped/,
		/InvalidStateError: Transition was aborted/,
	],
	integrations: [
		new Sentry.BrowserTracing(),
		new Sentry.Replay(),
	],
	replaysSessionSampleRate: 0.1,
	replaysOnErrorSampleRate: 1.0,
})
