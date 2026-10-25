import { api_request } from '@helpers/api.minmatar.org/client'
import type {
    TrainingAccountMove,
    TrainingAccountOptions,
    TrainingCharacter,
    TrainingGoalPatch,
    TrainingOverview,
    TrainingPlan,
    TrainingShipOption,
} from '@dtypes/api.minmatar.org'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/training`

const character_url = (character_id:number) => `${API_ENDPOINT}/characters/${character_id}`

export async function get_training_overview(access_token:string) {
    return await api_request<TrainingOverview>(`${API_ENDPOINT}/`, {
        token: access_token,
        error: 'Error fetching training',
    })
}

export async function get_training_character(access_token:string, character_id:number) {
    return await api_request<TrainingCharacter>(character_url(character_id), {
        token: access_token,
        error: 'Error fetching character',
    })
}

export async function get_training_plan(access_token:string, character_id:number, fitting_id:number) {
    return await api_request<TrainingPlan>(`${character_url(character_id)}/plans/${fitting_id}`, {
        token: access_token,
        error: 'Error fetching the training plan',
    })
}

export async function get_training_ships(access_token:string, character_id:number) {
    return await api_request<TrainingShipOption[]>(`${character_url(character_id)}/ships`, {
        token: access_token,
        error: 'Error fetching ships',
    })
}

export async function get_training_accounts(access_token:string, character_id:number) {
    return await api_request<TrainingAccountOptions>(`${character_url(character_id)}/accounts`, {
        token: access_token,
        error: 'Error fetching accounts',
    })
}

export async function add_training_goal(access_token:string, character_id:number, fitting_id:number) {
    return await api_request(`${character_url(character_id)}/goals`, {
        method: 'POST',
        token: access_token,
        body: { fitting_id },
    })
}

export async function update_training_goal(access_token:string, character_id:number, fitting_id:number, patch:TrainingGoalPatch) {
    return await api_request(`${character_url(character_id)}/goals/${fitting_id}`, {
        method: 'PATCH',
        token: access_token,
        body: patch,
    })
}

export async function remove_training_goal(access_token:string, character_id:number, fitting_id:number) {
    return await api_request(`${character_url(character_id)}/goals/${fitting_id}`, {
        method: 'DELETE',
        token: access_token,
    })
}

export async function set_not_for_fleets(access_token:string, character_id:number, not_for_fleets:boolean) {
    return await api_request(character_url(character_id), {
        method: 'PATCH',
        token: access_token,
        body: { not_for_fleets },
    })
}

export async function move_training_character(access_token:string, character_id:number, move:TrainingAccountMove) {
    return await api_request(`${character_url(character_id)}/account`, {
        method: 'PUT',
        token: access_token,
        body: move,
    })
}
