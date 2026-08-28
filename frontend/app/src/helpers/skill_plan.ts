import type { SkillsUI } from '@dtypes/layout_components'

export const SKILL_LEVEL_ROMAN: Record<number, string> = {
    1: 'I',
    2: 'II',
    3: 'III',
    4: 'IV',
    5: 'V',
}

export function format_skill_plan_line(skill_name: string, skill_level: number): string {
    return `${skill_name} ${SKILL_LEVEL_ROMAN[skill_level] ?? skill_level}`
}

export function format_skill_plan(skills: SkillsUI[]): string {
    return skills
        .map((skill) => format_skill_plan_line(skill.skill_name, skill.skill_level))
        .join('\n')
}
