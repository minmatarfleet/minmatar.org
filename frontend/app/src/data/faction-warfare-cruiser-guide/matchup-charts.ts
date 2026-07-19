import type { MatchupChart, MatchupRating } from './types'

export const matchupLegend = [
    { rating: '++' as const, label: 'Go for it champ', description: 'Very favorable matchup' },
    { rating: '+' as const, label: 'Try it, you might like it', description: 'Favorable matchup' },
    { rating: '=' as const, label: 'Fifty-Fifty', description: 'Even matchup' },
    { rating: '-' as const, label: 'Bad Idea', description: 'Unfavorable matchup' },
    { rating: '--' as const, label: 'Are you ok bud?', description: 'Very unfavorable matchup' },
    { rating: '?' as const, label: 'Still figuring it out', description: 'Meta unknown or not yet tested' },
]

/**
 * Axes use exact example-fit names from fittings.ts.
 * Row = high ground (inside the plex), column = low ground (sliding in).
 */
const brawlRows = [
    'Blaster Exequror Navy Issue',
    'Dual Rep Vexor Navy Issue',
    'Polarized Augoror Navy Issue',
    'HAM Caracal Navy Issue',
    '2X Neut HAM Osprey Navy Issue',
    'Brawl Arbitrator',
    'Dual Prop Stabber Fleet Issue',
    'Dual Prop Scythe Fleet Issue',
]

const kiteRows = [
    'Long Point Arbitrator',
    'Pulse Augoror Navy Issue',
    'Kite Omen Navy Issue',
    '250mm Rail Exequror Navy Issue',
    'RHML Osprey Navy Issue',
    'Armor RLML Scythe Fleet Issue',
    'Vulcan Stabber',
]

const t1Rows = [
    'Brawl Arbitrator',
    'Pulse Maller',
    'Beam Omen',
    'Neut Vexor',
    'XLASB HAM Bellicose',
    'AB XLASB Stabber',
]

const brawlMatrix: MatchupRating[][] = [
    // Blaster Exequror Navy Issue high
    ['=', '-', '+', '+', '=', '+', '+', '+'],
    // Dual Rep Vexor Navy Issue high
    ['+', '=', '+', '+', '=', '++', '++', '+'],
    // Polarized Augoror Navy Issue high
    ['-', '--', '=', '+', '=', '+', '+', '+'],
    // HAM Caracal Navy Issue high
    ['=', '-', '+', '=', '-', '+', '+', '='],
    // 2X Neut HAM Osprey Navy Issue high
    ['=', '=', '+', '+', '=', '+', '=', '-'],
    // Brawl Arbitrator high
    ['-', '--', '+', '=', '=', '=', '=', '='],
    // Dual Prop Stabber Fleet Issue high
    ['-', '--', '+', '=', '+', '+', '=', '='],
    // Dual Prop Scythe Fleet Issue high
    ['-', '-', '+', '+', '+', '+', '-', '='],
]

const kiteMatrix: MatchupRating[][] = [
    // Long Point Arbitrator high
    ['=', '-', '-', '-', '=', '-', '+'],
    // Pulse Augoror Navy Issue high
    ['+', '=', '=', '=', '+', '-', '+'],
    // Kite Omen Navy Issue high
    ['+', '=', '=', '=', '+', '-', '+'],
    // 250mm Rail Exequror Navy Issue high
    ['+', '=', '=', '=', '+', '=', '+'],
    // RHML Osprey Navy Issue high
    ['=', '-', '=', '-', '=', '--', '-'],
    // Armor RLML Scythe Fleet Issue high
    ['+', '+', '+', '=', '++', '=', '+'],
    // Vulcan Stabber high
    ['=', '-', '-', '-', '=', '-', '='],
]

const t1Matrix: MatchupRating[][] = [
    // Brawl Arbitrator high
    ['=', '+', '+', '-', '=', '+'],
    // Pulse Maller high
    ['-', '=', '=', '--', '-', '-'],
    // Beam Omen high
    ['-', '=', '=', '-', '=', '='],
    // Neut Vexor high
    ['+', '++', '+', '=', '+', '+'],
    // XLASB HAM Bellicose high
    ['=', '+', '=', '-', '=', '='],
    // AB XLASB Stabber high
    ['-', '+', '=', '-', '=', '='],
]

export const brawlingChart: MatchupChart = {
    id: 'brawling',
    title: 'Brawling Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: brawlRows,
    columns: brawlRows,
    matrix: brawlMatrix,
}

export const kitingChart: MatchupChart = {
    id: 'kiting',
    title: 'Kiting Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: kiteRows,
    columns: kiteRows,
    matrix: kiteMatrix,
}

export const t1Chart: MatchupChart = {
    id: 't1-cruisers',
    title: 'T1 Cruiser Matchup Chart',
    rowLabel: 'High ground',
    columnLabel: 'Low ground',
    rows: t1Rows,
    columns: t1Rows,
    matrix: t1Matrix,
}

export const matchupCharts = [brawlingChart, kitingChart, t1Chart]
