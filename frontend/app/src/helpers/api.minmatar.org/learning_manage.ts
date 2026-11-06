import type {
    LearningManageAward,
    LearningManageCertificate,
    LearningManageCertificateWrite,
    LearningManageGuide,
    LearningManageGuideWrite,
    LearningManageOnboarding,
    LearningManageSkillset,
    LearningManageSkillsetWrite,
} from '@dtypes/api.minmatar.org'
import { api_request } from '@helpers/api.minmatar.org/client'

const API_ENDPOINT = `${import.meta.env.API_URL}/api/learning/manage`

export const get_manage_guides = (token: string) =>
    api_request<LearningManageGuide[]>(`${API_ENDPOINT}/guides`, { token })

export const save_manage_guide = (token: string, slug: string | null, body: LearningManageGuideWrite) =>
    api_request<LearningManageGuide>(`${API_ENDPOINT}/guides${slug ? `/${encodeURIComponent(slug)}` : ''}`, {
        method: slug ? 'PUT' : 'POST',
        token,
        body,
    })

export const get_manage_certificates = (token: string) =>
    api_request<LearningManageCertificate[]>(`${API_ENDPOINT}/certificates`, { token })

export const save_manage_certificate = (
    token: string,
    slug: string | null,
    body: LearningManageCertificateWrite,
) =>
    api_request<LearningManageCertificate>(
        `${API_ENDPOINT}/certificates${slug ? `/${encodeURIComponent(slug)}` : ''}`,
        { method: slug ? 'PUT' : 'POST', token, body },
    )

export const change_manage_award = (token: string, revoke: boolean, body: LearningManageAward) =>
    api_request<unknown>(`${API_ENDPOINT}/awards${revoke ? '/revoke' : ''}`, { method: 'POST', token, body })

export const get_manage_onboarding = (token: string) =>
    api_request<LearningManageOnboarding[]>(`${API_ENDPOINT}/onboarding`, { token })

export const bump_manage_onboarding = (token: string, program_type: string) =>
    api_request<LearningManageOnboarding>(
        `${API_ENDPOINT}/onboarding/${encodeURIComponent(program_type)}/version`,
        { method: 'POST', token },
    )

export const get_manage_skillsets = (token: string) =>
    api_request<LearningManageSkillset[]>(`${API_ENDPOINT}/skillsets`, { token })

export const save_manage_skillset = (token: string, id: number | null, body: LearningManageSkillsetWrite) =>
    api_request<LearningManageSkillset>(`${API_ENDPOINT}/skillsets${id ? `/${id}` : ''}`, {
        method: id ? 'PUT' : 'POST',
        token,
        body,
    })

export const search_manage_skills = (token: string, q: string) =>
    api_request<{ name: string }[]>(`${API_ENDPOINT}/skillsets/skill-search?q=${encodeURIComponent(q)}`, { token })
