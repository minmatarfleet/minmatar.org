import type {
    MentorAction,
    MentorClassBody,
    MentorClassCreated,
    MentorClassDetail,
    MentorClassEdit,
    MentorClassOptions,
    MentorCreateRequest,
    MentorRequest,
    MentorSettings,
    MentorSettingsPatch,
    MentorSlots,
    MentoringView,
    MentorsAdmin,
    MentorsHome,
    MentorsMe,
    MentorsMetrics,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/learning/mentors`

const get = <T>(path: string, token: string) =>
    api_request<T>(`${API_ENDPOINT}${path}`, { method: 'GET', token })

const send = <T>(method: string, path: string, token: string, body?: unknown) =>
    api_request<T>(`${API_ENDPOINT}${path}`, { method, token, body })

export const get_mentors_home = (token: string) => get<MentorsHome>('', token)
export const get_mentors_me = (token: string) => get<MentorsMe>('/me', token)
export const get_mentors_past = (token: string) => get<MentorRequest[]>('/past', token)
export const get_mentor_class = (token: string, slug: string) =>
    get<MentorClassDetail>(`/classes/${encodeURIComponent(slug)}`, token)
export const get_mentoring = (token: string) => get<MentoringView>('/mentoring', token)
export const get_mentor_slots = (token: string, request_id: number) =>
    get<MentorSlots>(`/requests/${request_id}/slots`, token)
export const get_mentor_settings = (token: string) => get<MentorSettings>('/settings', token)
export const get_mentor_class_edit = (token: string, class_id: number) =>
    get<MentorClassEdit>(`/classes/${class_id}/edit`, token)
export const get_mentor_class_options = (token: string) =>
    get<MentorClassOptions>('/admin/class-options', token)
export const get_mentors_admin = (token: string) => get<MentorsAdmin>('/admin', token)
export const get_mentors_metrics = (token: string, period: number) =>
    get<MentorsMetrics>(`/admin/metrics?period=${period}`, token)

export const create_mentor_request = (token: string, body: MentorCreateRequest) =>
    send<MentorRequest>('POST', '/requests', token, body)
export const cancel_mentor_request = (token: string, request_id: number) =>
    send<MentorAction>('POST', `/requests/${request_id}/cancel`, token)
export const pass_mentor_request = (token: string, request_id: number) =>
    send<MentorAction>('POST', `/requests/${request_id}/pass`, token)
export const accept_mentor_request = (token: string, request_id: number, starts_at: string, bring: string) =>
    send<MentorAction>('POST', `/requests/${request_id}/accept`, token, { starts_at, bring })
export const send_mentor_feedback = (token: string, request_id: number, answer: string, note: string) =>
    send<MentorAction>('POST', `/requests/${request_id}/feedback`, token, { answer, note })
export const save_mentor_settings = (token: string, body: MentorSettingsPatch) =>
    send<MentorSettings>('PUT', '/settings', token, body)
export const apply_to_mentor = (token: string, note: string) =>
    send<MentorAction>('POST', '/apply', token, { note })
export const create_mentor_class = (token: string, body: MentorClassBody) =>
    send<MentorClassCreated>('POST', '/classes', token, body)
export const save_mentor_class = (token: string, class_id: number, body: MentorClassBody) =>
    send<MentorClassEdit>('PUT', `/classes/${class_id}/edit`, token, body)
export const invite_class_teacher = (token: string, class_id: number, character_name: string) =>
    send<MentorAction>('POST', `/classes/${class_id}/teachers`, token, { character_name })
export const teach_mentor_class = (token: string, class_id: number) =>
    send<MentorAction>('POST', `/classes/${class_id}/teach`, token)
export const stop_teaching_mentor_class = (token: string, class_id: number) =>
    send<MentorAction>('DELETE', `/classes/${class_id}/teach`, token)
export const set_mentor_class_status = (token: string, class_id: number, status: string, note: string = '') =>
    send<MentorAction>('PUT', `/admin/classes/${class_id}/status`, token, { status, note })
export const set_mentor_status = (token: string, mentor_id: number, status: string) =>
    send<MentorAction>('PUT', `/admin/mentors/${mentor_id}/status`, token, { status })
export const make_mentor = (token: string, character_name: string) =>
    send<MentorAction>('POST', '/admin/mentors', token, { character_name })
