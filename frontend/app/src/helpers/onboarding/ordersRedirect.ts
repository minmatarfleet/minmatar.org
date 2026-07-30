import {
    get_onboarding_status,
    ORDERS_ONBOARDING_PROGRAM_TYPE,
} from '@helpers/api.minmatar.org/onboarding'
import { safe_onboarding_return_path } from '@helpers/onboarding/srpRedirect'

export { safe_onboarding_return_path }

export async function should_redirect_to_orders_onboarding(
    auth_token: string,
): Promise<boolean> {
    try {
        const st = await get_onboarding_status(auth_token, ORDERS_ONBOARDING_PROGRAM_TYPE)
        return !st.is_current
    } catch {
        // Missing program row or API error — do not 500 the orders page.
        return false
    }
}

export async function is_orders_onboarding_required(auth_token: string): Promise<boolean> {
    try {
        const st = await get_onboarding_status(auth_token, ORDERS_ONBOARDING_PROGRAM_TYPE)
        return !st.is_current
    } catch {
        return false
    }
}
