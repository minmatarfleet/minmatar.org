// Types for the quarterly community survey feature.

export interface SurveyQuestion {
    key: string
    type: 'scale5' | 'enps' | 'agree' | 'single' | 'multi' | 'matrix' | 'text'
    label: string
    help: string
    choices: string[]
    rows: {
        key: string
        label: string
        hint?: string
        chief_id?: number | null
        chief_name?: string
        groups?: {
            name: string
            chief_id?: number | null
            chief_name?: string
        }[]
    }[]
    required: boolean
    trendable: boolean
    group?: string
    scale_labels: string[] | null
    scale_kind: '' | 'rating' | 'diverging'
    context?: {
        fcs: { character_id: number; character_name: string }[]
        recent_fleets: {
            title: string
            date: string
            fc_id?: number | null
            fc_name?: string
            objective?: string
        }[]
        resources: { title: string; url: string }[]
    } | null
}

export interface SurveyBlock {
    key: string
    title: string
    description: string
    questions: SurveyQuestion[]
}

export interface SurveyQuestions {
    campaign_id: number
    definition_key: string
    title: string
    member_blocks: SurveyBlock[]
}

export interface TribeRef {
    key: string
    label: string
    chief_id: number | null
    chief_name: string
    hint: string
}

export interface CorpHistoryEntry {
    corporation_id: number
    name: string
    ticker: string
    days: number
    is_current: boolean
    is_academy: boolean
}

export interface MemberContext {
    character_id: number | null
    character_name: string
    corporation_id: number | null
    corporation_name: string
    ceo_id: number | null
    ceo_name: string
    corp_history: CorpHistoryEntry[]
    graduated: boolean
    prime_time: string
    tribes: TribeRef[]
    tribe_names: string[]
    community_status: string
    tenure_days: number | null
    tenure_cohort: string
    joined_at: string | null
    fleets_attended_quarter: number
    activity_tier: string
    role_flags: string[]
    guides_completed: number
    persona: string
    tenure_note: string
    fleets_note: string
    guides_note: string
    timezone_note: string
}

export interface SurveyCampaign {
    id: number
    year: number
    quarter: number
    definition_key: string
    title: string
    status: 'draft' | 'open' | 'closed'
    opens_at: string | null
    closes_at: string | null
    response_count: number
}

export interface ActiveSurvey {
    campaign: SurveyCampaign | null
    has_responded: boolean
}

export interface MyResponse {
    answers: Record<string, any>
    has_responded: boolean
    submitted_at: string | null
}

export interface SurveyAnswerInput {
    question_key: string
    value: any
}

export interface SubmitResult {
    ok: boolean
    response_id: number | null
    detail: string
}

export interface GivebackCard {
    personal: {
        fleets_flown: number
        doctrines_ready: number
        guides_completed: number
        srp_count: number
        srp_isk: number
        tribe: string
    }
    community: {
        active_pilots: number | null
    }
}

export interface ChangelogEntry {
    heading: string
    body_markdown: string
    sort_order: number
}

export interface SurveyAggregate {
    question_key: string
    segment_key: string
    n: number
    mean: number | null
    distribution: Record<string, number>
}

export interface SurveyResults {
    campaign_id: number
    segment_key: string
    aggregates: SurveyAggregate[]
}

export interface CorpReportQuestion {
    question_key: string
    label: string
    mean: number | null
    n: number
}

export interface CorpReportEntry {
    corp: string
    n: number
    suppressed: boolean
    questions: CorpReportQuestion[]
}

export interface CorpReport {
    campaign_id: number
    scope: 'all' | 'own'
    min_n: number
    corps: CorpReportEntry[]
}
