import { marked } from 'marked';
import { get_app_url } from '@helpers/env'

export const renderer = new marked.Renderer()

const linkRenderer = renderer.link

renderer.link = (href, title, text) => {
  const localLink = href.startsWith(`${get_app_url()}`)
  const html = linkRenderer.call(renderer, href, title, text)
  return localLink ? html : html.replace(/^<a /, `<a target="_blank" rel="noreferrer noopener nofollow" `)
}