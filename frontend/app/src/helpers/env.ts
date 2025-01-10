const API_URL = import.meta.env.API_URL
const APP_URL = import.meta.env.APP_URL
const PROD_ERROR_MESSAGES = import.meta.env.PROD_ERROR_MESSAGES ?? false

export const is_dev_mode = () => {
    return import.meta.env.DEV;
}

export const is_prod_mode = () => {
    return import.meta.env.PROD;
}

export const get_auth_url = () => {
    return `${API_URL}/api/users/login?redirect_url=${APP_URL}/auth/login`
}

export const get_friend_auth_url = () => {
    return `${API_URL}/api/users/login?redirect_url=${APP_URL}/friend/login`
}

export const get_api_url = () => {
    return API_URL
}

export const get_app_url = (path:string = '') => {
    return `${APP_URL}${path}`
}

export const prod_error_messages = () => {
    return PROD_ERROR_MESSAGES === 'true'
}

export const is_disabled_ccpwgl = () => {
    return import.meta.env.DISABLED_CCPWGL ?? true
}