// The "you are leaving the website" disclaimer wiring shared by Button, StylessButton and ExternalLink.
// Every value that reaches an Alpine expression goes through JSON.stringify, so a quote in the
// title, partial path or href cannot end the string early and run as code.

export interface ExternalLinkOptions {
    href:              string;
    title:             string;
    partial:           string;
    x_data_elements?:  string;
}

export interface ExternalLinkAttributes {
    x_data:            string;
    x_on_click_prevent: string;
}

export const external_link_attributes = ({
    href,
    title,
    partial,
    x_data_elements = '',
}: ExternalLinkOptions): ExternalLinkAttributes => {
    const href_js = JSON.stringify(href ?? '')
    const extra = x_data_elements.trim()

    return {
        x_data: `{
        hide_external_link_disclaimer: $persist(false),
        show_external_link_disclaimer() {
            const root_data = Alpine.$data(document.body)
            if (!root_data || !root_data.show_alert_dialog) return Promise.resolve(false)
            return root_data.show_alert_dialog({
                title: ${JSON.stringify(title)},
                partial: ${JSON.stringify(partial)},
                accept_href: ${href_js},
            })
        }${extra ? `,
        ${extra}` : ''}
    }`,
        x_on_click_prevent: `hide_external_link_disclaimer ? window.open(${href_js}, '_blank') : show_external_link_disclaimer()`,
    }
}
