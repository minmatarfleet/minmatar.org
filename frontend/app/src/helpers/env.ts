export const is_dev_mode = () => {
    return import.meta.env.DEV;
}

export const is_prod_mode = () => {
    return import.meta.env.PROD;
}

export const get_auth_url = () => {
    return import.meta.env.MINMATAR_AUTH
}