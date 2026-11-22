import { is_prod_mode } from '@helpers/env'

/**
 * The close promise every site-wide dialog shares: it settles on the first
 * click anywhere in <body> that lands on an element carrying `<css>-action`
 * (the backdrop, the accept/cancel buttons, the corner button), so a second
 * click on accept finds no listener and resolves nothing twice.
 */
export const dialog_close_member = (name: string) => {
    const action = `${name.replaceAll('_', '-')}-action`
    return `
    ${name}_close() {
        const body = document.querySelector("body");

        return new Promise(function (resolve, reject) {
            var listener = event => {
                if (event.target.hasAttribute('${action}')) {
                    body.removeEventListener('click', listener);
                    resolve({
                        action: event.target.getAttribute('${action}')
                    });
                }
            };
            body.addEventListener('click', listener);
        });
    },`
}

/**
 * State and `show_<name>()` for the content modal and its persistent twin.
 * `<name>_shown` counts openings: DialogBase watches it to let htmx pick up the
 * hx-* attributes Alpine bound for this opening (the only htmx.process left).
 */
export const modal_x_data = (name: 'modal' | 'persistent_modal') => `
    ${name}_open: false,
    ${name}_shown: 0,
    ${name}_content: '',
    ${name}_partial: '',
    ${name}_partial_params: '',
    async show_${name}(args) {
        const defaults =  {
            content: '',
            partial: '',
            return_on_accept: true,
        }

        const properties = {...defaults, ...args}

        if (this.${name}_partial != properties.partial) {
            this.${name}_content = ''
            ${!is_prod_mode() ? `console.log('Modal cache cleared!')` : ''}
        }

        if (properties.partial_params && (JSON.stringify(properties.partial_params) != JSON.stringify(this.${name}_partial_params))) {
            this.${name}_content = ''
            ${!is_prod_mode() ? `console.log('Modal cache cleared!')` : ''}
        }

        if (properties.partial) {
            this.${name}_content = '<div class="[ rifter-modal ]">'+this.rifter_animation+'</div>'
        } else
            this.${name}_content = properties.content

        this.${name}_return_on_accept = properties.return_on_accept
        this.${name}_partial = properties.partial

        if (properties.partial_params)
            this.${name}_partial_params = properties.partial_params
        else
            this.${name}_partial_params = ''

        this.${name}_open = true
        this.${name}_shown++

        return new Promise((resolve) => {
            this.${name}_close().then((result) => {
                this.${name}_open = false
                resolve(result.action == 'accept' ? this.${name}_return_on_accept : false)
            })
        })
    },${dialog_close_member(name)}`
