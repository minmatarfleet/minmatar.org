import {
    accept_mentor_request,
    apply_to_mentor,
    cancel_mentor_request,
    create_mentor_request,
    invite_class_teacher,
    make_mentor,
    pass_mentor_request,
    save_mentor_settings,
    send_mentor_feedback,
    set_mentor_class_status,
    set_mentor_status,
    stop_teaching_mentor_class,
    teach_mentor_class,
} from '@helpers/api.minmatar.org/mentors'
import { form_numbers, form_strings } from '@helpers/mentors'

/**
 * Every POST a Mentors partial takes. The partials post their forms here with
 * a `mode` and render again, so each one shows the result of its own action.
 */
export type MentorMode =
    | 'request' | 'cancel' | 'pass' | 'accept' | 'feedback' | 'apply'
    | 'save_settings' | 'teach' | 'stop' | 'invite_teacher'
    | 'class_status' | 'mentor_status' | 'make_mentor'

export interface MentorActionResult {
    ok: boolean;
    message: string;
    /** After `request`: the mentor who was asked, for the "Request sent" line. */
    mentor_name?: string;
}

const number_of = (form: FormData, params: URLSearchParams, key: string): number =>
    parseInt(String(form.get(key) ?? params.get(key) ?? '0')) || 0

const text_of = (form: FormData, key: string): string => String(form.get(key) ?? '').trim()

/** The class time from the accept form: a suggested slot, or a date and time typed in EVE time. */
export function picked_start(form: FormData): string {
    const slot = text_of(form, 'slot')
    if (slot && slot !== 'other')
        return slot
    const date = text_of(form, 'date')
    const time = text_of(form, 'time')
    return date && time ? `${date}T${time}:00Z` : ''
}

export async function run_mentor_action(
    token: string,
    mode: MentorMode,
    form: FormData,
    params: URLSearchParams,
): Promise<MentorActionResult> {
    const request_id = number_of(form, params, 'request_id')
    const class_id = number_of(form, params, 'class_id')
    try {
        if (mode === 'request') {
            const created = await create_mentor_request(token, {
                mentor_id: number_of(form, params, 'mentor_id'),
                class_id,
                note: text_of(form, 'note'),
                weekday_brackets: form_strings(form.getAll('weekday_brackets')),
                weekend_brackets: form_strings(form.getAll('weekend_brackets')),
                days: form_numbers(form.getAll('days')),
            })
            return { ok: true, message: '', mentor_name: created.mentor.name }
        }
        if (mode === 'accept') {
            const starts_at = picked_start(form)
            if (!starts_at)
                return { ok: false, message: 'Pick a time for the class.' }
            const result = await accept_mentor_request(token, request_id, starts_at, text_of(form, 'bring'))
            return { ok: true, message: result.message }
        }
        if (mode === 'save_settings') {
            await save_mentor_settings(token, {
                weekday_brackets: form_strings(form.getAll('weekday_brackets')),
                weekend_brackets: form_strings(form.getAll('weekend_brackets')),
                days: form_numbers(form.getAll('days')),
                classes_per_week: Math.max(1, number_of(form, params, 'classes_per_week')),
                taking_requests: form.get('taking_requests') === 'on',
            })
            return { ok: true, message: '' }
        }
        const result =
            mode === 'cancel' ? await cancel_mentor_request(token, request_id) :
            mode === 'pass' ? await pass_mentor_request(token, request_id) :
            mode === 'feedback' ? await send_mentor_feedback(token, request_id, text_of(form, 'answer'), text_of(form, 'note')) :
            mode === 'apply' ? await apply_to_mentor(token, text_of(form, 'note')) :
            mode === 'teach' ? await teach_mentor_class(token, class_id) :
            mode === 'stop' ? await stop_teaching_mentor_class(token, class_id) :
            mode === 'invite_teacher' ? await invite_class_teacher(token, class_id, text_of(form, 'character_name')) :
            mode === 'class_status' ? await set_mentor_class_status(token, class_id, text_of(form, 'status'), text_of(form, 'note')) :
            mode === 'mentor_status' ? await set_mentor_status(token, number_of(form, params, 'mentor_id'), text_of(form, 'status')) :
            mode === 'make_mentor' ? await make_mentor(token, text_of(form, 'character_name')) :
            null
        return result ? { ok: true, message: result.message } : { ok: false, message: 'Unknown action.' }
    } catch (error) {
        return { ok: false, message: (error as Error).message }
    }
}

/** Reads the mode and runs it when the partial was posted to. */
export async function handle_mentor_post(request: Request, url: URL, token: string): Promise<MentorActionResult | null> {
    const mode = url.searchParams.get('mode') as MentorMode | null
    if (request.method !== 'POST' || !mode)
        return null
    const form = await request.formData()
    return run_mentor_action(token, mode, form, url.searchParams)
}
