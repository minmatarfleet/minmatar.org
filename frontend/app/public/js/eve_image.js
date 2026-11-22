// The image-server URL helpers for Alpine expressions in the browser. The same
// URLs src/helpers/eve_image.ts builds on the server (keep the two in step).
if (!window.__eve_image_js_bound) {
    window.__eve_image_js_bound = true

    const image_url = (collection, id, variant, size) => `https://images.evetech.net/${collection}/${id}/${variant}?size=${size}`

    window.get_item_icon = (id, size = 64) => image_url('types', id, size <= 64 ? 'icon' : 'render', size)
    window.get_type_icon = (id, size = 64) => image_url('types', id, 'icon', size)
    window.get_type_render = (id, size = 512) => image_url('types', id, 'render', size)
    window.get_bpc_icon = (id, is_copy = false, size = 64) => image_url('types', id, is_copy ? 'bpc' : 'bp', size)
    window.get_player_icon = (id, size = 64) => image_url('characters', id, 'portrait', size)
    window.get_alliance_logo = (id, size = 32) => image_url('alliances', id, 'logo', size)
    window.get_corporation_logo = (id, size = 32) => image_url('corporations', id, 'logo', size)
}
