// @vitest-environment node
import { expect, test, vi } from 'vitest'

const api = vi.hoisted(() => ({ get_locations: vi.fn() }))
vi.mock('@helpers/api.minmatar.org/locations', () => ({ get_locations: api.get_locations }))

import { form_up_label, has_deployment, staging_location } from '@helpers/fleet_form_up'
import { fetch_schedule_locations } from '@helpers/fetching/fleet_schedule'
import type { FleetItem } from '@dtypes/layout_components'

const home = { location_id: 1, short_name: 'Home Station', staging_active: true, deployment_active: false }
const forward = { location_id: 2, short_name: 'Forward Station', staging_active: false, deployment_active: true }
const other = { location_id: 3, short_name: 'Jita', staging_active: false, deployment_active: false }
const labels = { staging: 'Staging', deployment: 'Deployment' }

test('the staging is the default form-up', () => {
    expect(staging_location([forward, home, other])).toBe(home)
    expect(staging_location([forward])).toBeNull()
})

test('the form-up select only shows while deployed', () => {
    expect(has_deployment([home, other])).toBe(false)
    expect(has_deployment([home, forward])).toBe(true)
})

test('form-up labels name the staging and deployments', () => {
    expect(form_up_label(home, labels)).toBe('Home Station · Staging')
    expect(form_up_label(forward, labels)).toBe('Forward Station · Deployment')
    expect(form_up_label(other, labels)).toBe('Jita')
})

const fleet = (location:string) => ({ id: 1, location }) as unknown as FleetItem

test('one form-up location: no location filter, no lookup', async () => {
    api.get_locations.mockReset()
    expect(await fetch_schedule_locations([fleet('Home - Station'), fleet('Home - Station')])).toEqual([])
    expect(api.get_locations).not.toHaveBeenCalled()
})

test('several form-up locations are labelled by short name', async () => {
    api.get_locations.mockResolvedValue([
        { location_name: 'Home - Station', short_name: 'Home Station' },
    ])
    expect(await fetch_schedule_locations([fleet('Home - Station'), fleet('Forward - Outpost')])).toEqual([
        { name: 'Home - Station', label: 'Home Station' },
        { name: 'Forward - Outpost', label: 'Forward' },
    ])
})
