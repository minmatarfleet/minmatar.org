/**
 * Fleet form-up locations: the home staging and any deployment the
 * alliance runs next to it.
 */

interface FormUpLocation {
    location_id:        number;
    short_name:         string;
    staging_active:     boolean;
    deployment_active?: boolean;
}

/** The home staging, the default form-up for a new fleet. */
export function staging_location<T extends FormUpLocation>(locations:T[]):T | null {
    return locations.find(location => location.staging_active) ?? null
}

/** True while any form-up location is a deployment. */
export function has_deployment(locations:FormUpLocation[]):boolean {
    return locations.some(location => location.deployment_active)
}

/** "Short name · Staging" / "Short name · Deployment", else the short name. */
export function form_up_label(location:FormUpLocation, labels:{ staging:string, deployment:string }):string {
    if (location.staging_active) return `${location.short_name} · ${labels.staging}`
    if (location.deployment_active) return `${location.short_name} · ${labels.deployment}`
    return location.short_name
}
