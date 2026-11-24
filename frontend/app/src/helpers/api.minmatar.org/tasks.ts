import type {
    MyTasks,
    TaskAssignees,
    TaskDigest,
    TaskDigestPatch,
    TaskCount,
    TaskCreate,
    TaskDetail,
    TaskItem,
    TaskPreferences,
    TaskPreferencesPatch,
    TaskRuleSetting,
    TaskRuleSettingPatch,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/tasks`

/** The actions a task row can post (TaskItem.actions lists the allowed ones). */
export const TASK_ACTIONS = ['done', 'snooze', 'not_now', 'bring_back', 'hand_back', 'take', 'keep', 'let_close', 'thank'] as const
export type TaskAction = typeof TASK_ACTIONS[number]

export function is_task_action(action:string | null | undefined): action is TaskAction {
    return TASK_ACTIONS.includes(action as TaskAction)
}

/** Everything waiting on the pilot. Refreshes their own automatic tasks first. */
export async function get_my_tasks(access_token:string) {
    return await api_request<MyTasks>(`${API_ENDPOINT}/mine`, {
        token: access_token,
        error: 'Error fetching your tasks',
    }) as MyTasks
}

export async function get_my_task_count(access_token:string) {
    return await api_request<TaskCount>(`${API_ENDPOINT}/mine/count`, {
        token: access_token,
        error: 'Error fetching your task count',
    }) as TaskCount
}

export async function get_task(access_token:string, task_id:number) {
    return await api_request<TaskDetail>(`${API_ENDPOINT}/${task_id}`, {
        token: access_token,
        error: 'Error fetching the task',
    }) as TaskDetail
}

export async function post_task_action(access_token:string, task_id:number, action:TaskAction) {
    return await api_request<TaskItem>(`${API_ENDPOINT}/${task_id}/actions/${action}`, {
        method: 'POST',
        token: access_token,
        error: 'Error updating the task',
    }) as TaskItem
}

export async function post_task_comment(access_token:string, task_id:number, body:string) {
    return await api_request<TaskDetail>(`${API_ENDPOINT}/${task_id}/comments`, {
        method: 'POST',
        token: access_token,
        body: { body },
        error: 'Error posting the comment',
    }) as TaskDetail
}

export async function create_task(access_token:string, task:TaskCreate) {
    return await api_request<TaskItem>(API_ENDPOINT, {
        method: 'POST',
        token: access_token,
        body: task,
        error: 'Error creating the task',
    }) as TaskItem
}

export async function get_task_assignees(access_token:string, query:string) {
    const params = new URLSearchParams({ q: query })
    return await api_request<TaskAssignees>(`${API_ENDPOINT}/assignees?${params}`, {
        token: access_token,
        error: 'Error searching pilots',
    }) as TaskAssignees
}

export async function get_task_rules(access_token:string) {
    return await api_request<TaskRuleSetting[]>(`${API_ENDPOINT}/rules`, {
        token: access_token,
        error: 'Error fetching automatic tasks',
    }) ?? []
}

export async function patch_task_rule(access_token:string, rule:string, patch:TaskRuleSettingPatch) {
    return await api_request<TaskRuleSetting>(`${API_ENDPOINT}/rules/${encodeURIComponent(rule)}`, {
        method: 'PATCH',
        token: access_token,
        body: patch,
        error: 'Error saving the automatic task',
    }) as TaskRuleSetting
}

export async function get_task_preferences(access_token:string) {
    return await api_request<TaskPreferences>(`${API_ENDPOINT}/preferences`, {
        token: access_token,
        error: 'Error fetching your task settings',
    }) as TaskPreferences
}

export async function patch_task_preferences(access_token:string, patch:TaskPreferencesPatch) {
    return await api_request<TaskPreferences>(`${API_ENDPOINT}/preferences`, {
        method: 'PATCH',
        token: access_token,
        body: patch,
        error: 'Error saving your task settings',
    }) as TaskPreferences
}

export async function get_task_digest(access_token:string) {
    return await api_request<TaskDigest>(`${API_ENDPOINT}/digest`, {
        token: access_token,
        error: 'Error fetching the weekly list settings',
    }) as TaskDigest
}

export async function patch_task_digest(access_token:string, patch:TaskDigestPatch) {
    return await api_request<TaskDigest>(`${API_ENDPOINT}/digest`, {
        method: 'PATCH',
        token: access_token,
        body: patch,
        error: 'Error saving the weekly list settings',
    }) as TaskDigest
}
