import type { MatchupChart } from './types'

export const matchupLegend = [
    { rating: '++' as const, label: 'Go for it champ', description: 'Very favorable matchup' },
    { rating: '+' as const, label: 'Try it, you might like it', description: 'Favorable matchup' },
    { rating: '=' as const, label: 'Fifty-Fifty', description: 'Even matchup' },
    { rating: '-' as const, label: 'Bad Idea', description: 'Unfavorable matchup' },
    { rating: '--' as const, label: 'Are you ok bud?', description: 'Very unfavorable matchup' },
    { rating: '?' as const, label: 'Still figuring it out', description: 'Meta unknown or not yet tested' },
]

/** High-ground rows vs low-ground columns for common navy + top T1 scram-range lines. */
export const brawlingChart: MatchupChart = {
    id: 'scram-range',
    title: 'Scram-Range Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: [
        'Rocket Hookbill',
        'Blaster Comet',
        'Arty Firetail',
        'Scram Vigil Fleet',
        'AC Rifter',
        'Tristan',
        'MASB Breacher',
    ],
    columns: [
        'Rocket Hookbill',
        'Blaster Comet',
        'Arty Firetail',
        'Scram Vigil Fleet',
        'AC Rifter',
        'Tristan',
        'MASB Breacher',
    ],
    matrix: [
        ['=', '++', '+', '+', '++', '++', '++'],
        ['--', '=', '=', '-', '++', '++', '+'],
        ['-', '=', '=', '=', '++', '++', '+'],
        ['-', '+', '=', '=', '++', '++', '+'],
        ['--', '--', '--', '--', '=', '=', '-'],
        ['--', '--', '--', '--', '=', '=', '='],
        ['--', '-', '-', '-', '+', '=', '='],
    ],
}

export const kitingChart: MatchupChart = {
    id: 'kiting',
    title: 'Kiting Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: [
        'Beam Slicer',
        'Pulse Slicer',
        'MWD Comet',
        'Arty Firetail (web kite)',
        'Web Kite Vigil Fleet',
        'LML Hookbill',
    ],
    columns: [
        'Beam Slicer',
        'Pulse Slicer',
        'MWD Comet',
        'Arty Firetail (web kite)',
        'Web Kite Vigil Fleet',
        'LML Hookbill',
    ],
    matrix: [
        ['=', '+', '+', '+', '=', '+'],
        ['-', '=', '+', '=', '-', '+'],
        ['-', '-', '=', '=', '-', '='],
        ['-', '=', '=', '=', '-', '+'],
        ['=', '+', '+', '+', '=', '+'],
        ['-', '-', '=', '-', '-', '='],
    ],
}

export const matchupCharts = [brawlingChart, kitingChart]
