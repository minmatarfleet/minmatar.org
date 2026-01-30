
import { useTranslations, useTranslatedPath } from '@i18n/utils';

import { marked } from 'marked';
import { get_app_url } from '@helpers/env'

export const renderer = new marked.Renderer()

const linkRenderer = renderer.link

renderer.link = (href, title, text) => {
	let replace = ''

	const localLink = href.startsWith(`${get_app_url()}`) || href.startsWith('/')

	if (!localLink) {
		const lang = 'en'
		const t = useTranslations(lang)
		const translatePath = useTranslatedPath(lang)

		const anchor = `target="_blank"
			rel="nofollow noopener noreferrer"
			x-data="{
				hide_external_link_disclaimer: $persist(false),
				show_external_link_disclaimer() {
					show_alert_dialog({
						title: '${t('leaving_website')}',
						partial: '${translatePath('/partials/external_link_disclaimer_dialog/')}',
					}).then(accepted => {
						if (accepted) window.open('HREF', '_blank')
					})
				}
			}"
			x-on:click.prevent="hide_external_link_disclaimer ? window.open('HREF', '_blank') : show_external_link_disclaimer()"`

		replace = anchor.replaceAll('HREF', href)
	}

	const html = linkRenderer.call(renderer, href, title, text)
	return localLink ? html : html.replace(/^<a /, `<a ${replace} `)
}