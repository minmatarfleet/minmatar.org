import type { MatchupChart } from './types'

export const matchupLegend = [
    { rating: '++' as const, label: 'Go for it champ', description: 'Very favorable matchup' },
    { rating: '+' as const, label: 'Try it, you might like it', description: 'Favorable matchup' },
    { rating: '=' as const, label: 'Fifty-Fifty', description: 'Even matchup' },
    { rating: '-' as const, label: 'Bad Idea', description: 'Unfavorable matchup' },
    { rating: '--' as const, label: 'Are you ok bud?', description: 'Very unfavorable matchup' },
]

export const brawlingChart: MatchupChart = {
    id: 'brawling',
    title: 'Brawling Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: [
        'Catalyst Blaster',
        'Catalyst 10mn',
        'Coercer Dual Neut',
        'Coercer Brawl',
        'Cormorant MASB',
        'Cormorant Buffer',
        'Thrasher AC No Web',
        'Thrasher AC Web',
    ],
    columns: [
        'Catalyst Blaster',
        'Catalyst 10mn',
        'Coercer Dual Neut',
        'Coercer Brawl',
        'Cormorant MASB',
        'Cormorant Buffer',
        'Thrasher AC No Web',
        'Thrasher AC Web',
    ],
    matrix: [
        ['=', '+', '--', '++', '-', '++', '++', '++'],
        ['+', '=', '++', '=', '++', '++', '++', '++'],
        ['++', '--', '=', '++', '++', '++', '--', '--'],
        ['--', '=', '--', '=', '=', '=', '+', '='],
        ['+', '-', '--', '++', '=', '+', '++', '++'],
        ['=', '+', '--', '++', '-', '=', '++', '++'],
        ['-', '--', '++', '-', '--', '--', '=', '++'],
        ['=', '+', '++', '=', '-', '-', '--', '='],
    ],
}

export const kitingChart: MatchupChart = {
    id: 'kiting',
    title: 'Kiting Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: [
        'Catalyst 10mn',
        'Beam Coercer',
        'Pulse Coercer',
        'Cormorant 10mn',
        'Thrasher 5mn',
        'Thrasher 1mn dual web',
    ],
    columns: [
        'Catalyst 10mn',
        'Beam Coercer',
        'Pulse Coercer',
        'Cormorant 10mn',
        'Thrasher 5mn',
        'Thrasher 1mn dual web',
    ],
    matrix: [
        ['=', '-', '-', '-', '+', '-'],
        ['++', '=', '+', '++', '+', '+'],
        ['+', '-', '=', '++', '+', '+'],
        ['+', '+', '+', '=', '+', '='],
        ['-', '-', '-', '-', '=', '-'],
        ['+', '=', '=', '=', '++', '='],
    ],
}

export const matchupCharts = [brawlingChart, kitingChart]
