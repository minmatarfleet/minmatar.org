import type { Tracking } from '@dtypes/layout_components'
import { eve_clock } from '@helpers/fetching/fleet_schedule'

export type CommandStepState = 'done' | 'next' | 'todo'

export interface CommandStep {
    key: 'scheduled' | 'ships' | 'start' | 'advert' | 'free_move' | 'motd'
    label: string
    detail: string
    state: CommandStepState
}

export interface CommandStepsInput {
    start_time: Date
    tracking: Tracking | null | undefined
    disable_motd?: boolean
    /** The fleet has ships to pick: a doctrine or fleet fittings. */
    has_ships: boolean
}

/**
 * The FC's road to form-up, in order: scheduled, ships set, started, then the
 * in-game checks tracking reads (advert, free move, MOTD). The first step not
 * done is `next`; the rest wait. The Command tab lists them and its tab label
 * names the next one.
 */
export const command_steps = (input:CommandStepsInput, t:(key:string) => string):CommandStep[] => {
    const tracking = input.tracking ?? null
    const tracking_started = Boolean(tracking?.start_time)
    const pending_detail = t('fleets.command.after_start')

    const steps:Omit<CommandStep, 'state'>[] = []
    const done:boolean[] = []
    const add = (step:Omit<CommandStep, 'state'>, is_done:boolean) => { steps.push(step); done.push(is_done) }

    add({ key: 'scheduled', label: t('fleets.setup.scheduled'), detail: t('fleets.eve_clock').replace('{time}', eve_clock(input.start_time)) }, true)
    add({
        key: 'ships',
        label: t('fleets.command.ships_set'),
        detail: input.has_ships ? t('fleets.setup.done') : t('fleets.command.ships_missing'),
    }, input.has_ships)
    add({
        key: 'start',
        label: tracking_started ? t('fleets.setup.pinged') : t('fleets.command.start'),
        detail: tracking_started ? t('fleets.setup.since').replace('{time}', eve_clock(tracking!.start_time)) : t('fleets.command.start_detail'),
    }, tracking_started)
    add({
        key: 'advert',
        label: t('fleets.setup.advert'),
        detail: !tracking_started ? pending_detail : tracking?.is_registered ? t('fleets.setup.advert_done') : t('fleets.setup.advert_fix'),
    }, Boolean(tracking?.is_registered))
    add({
        key: 'free_move',
        label: t('fleets.setup.free_move'),
        detail: !tracking_started ? pending_detail : tracking?.is_free_move ? t('fleets.setup.free_move_done') : t('fleets.setup.free_move_fix'),
    }, Boolean(tracking?.is_free_move))
    add({
        key: 'motd',
        label: t('fleets.setup.motd'),
        detail: input.disable_motd ? t('fleets.setup.motd_off') :
            !tracking_started ? pending_detail :
            tracking?.has_motd ? t('fleets.setup.motd_done') : t('fleets.setup.motd_fix'),
    }, Boolean(input.disable_motd) || Boolean(tracking?.has_motd))

    const next = done.findIndex(is_done => !is_done)
    return steps.map((step, index) => ({
        ...step,
        state: done[index] ? 'done' : index === next ? 'next' : 'todo',
    }))
}

/** The step the FC should do now, or null when everything is done. */
export const next_command_step = (steps:CommandStep[]):CommandStep | null =>
    steps.find(step => step.state === 'next') ?? null
