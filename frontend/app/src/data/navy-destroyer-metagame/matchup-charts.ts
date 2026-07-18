import type { MatchupChart } from './types'

export const matchupLegend = [
    { rating: '++' as const, label: 'Go for it champ', description: 'Very favorable matchup' },
    { rating: '+' as const, label: 'Try it, you might like it', description: 'Favorable matchup' },
    { rating: '=' as const, label: 'Fifty-Fifty', description: 'Even matchup' },
    { rating: '-' as const, label: 'Bad Idea', description: 'Unfavorable matchup' },
    { rating: '--' as const, label: 'Are you ok bud?', description: 'Very unfavorable matchup' },
    { rating: '?' as const, label: 'Still figuring it out', description: 'Meta unknown or not yet tested' },
]

export const brawlingChart: MatchupChart = {
    id: 'brawling',
    title: 'Brawling Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: [
        'Blaster Catalyst Navy Issue',
        '10mn Catalyst Navy Issue',
        '2X Neut Coercer Navy Issue',
        'Pulse Coercer Navy Issue',
        'Dual MASB Cormorant Navy Issue',
        'Buffer Cormorant Navy Issue',
        'AC Thrasher Fleet Issue (no web)',
        'AC Thrasher Fleet Issue (web)',
    ],
    columns: [
        'Blaster Catalyst Navy Issue',
        '10mn Catalyst Navy Issue',
        '2X Neut Coercer Navy Issue',
        'Pulse Coercer Navy Issue',
        'Dual MASB Cormorant Navy Issue',
        'Buffer Cormorant Navy Issue',
        'AC Thrasher Fleet Issue (no web)',
        'AC Thrasher Fleet Issue (web)',
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
        '10mn Catalyst Navy Issue',
        'Beam Coercer Navy Issue',
        'Pulse Coercer Navy Issue',
        '10mn Cormorant Navy Issue',
        'Arty Thrasher Fleet Issue',
        '280 Double-Web Thrasher Fleet Issue',
    ],
    columns: [
        '10mn Catalyst Navy Issue',
        'Beam Coercer Navy Issue',
        'Pulse Coercer Navy Issue',
        '10mn Cormorant Navy Issue',
        'Arty Thrasher Fleet Issue',
        '280 Double-Web Thrasher Fleet Issue',
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
