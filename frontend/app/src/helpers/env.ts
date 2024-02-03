export const is_dev_mode = () => {
    return import.meta.env.DEV;
}

export const is_prod_mode = () => {
    return import.meta.env.PROD;
}

export const get_auth_url = () => {
    API_URL = import.meta.env.API_URL
    APP_URL = import.meta.env.APP_URL
    return `${API_URL}/api/auth/login?redirect_uri=${APP_URL}/auth/login`
}

export const get_api_url = () => {
    return import.meta.env.API_URL
}

export const get_app_url = () => {
    return import.meta.env.APP_URL
}
