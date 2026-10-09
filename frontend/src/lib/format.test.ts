import { describe, expect, it } from 'vitest'
import { columnDecimals, columnLabel, formatCell, formatMs, formatRowCount } from './format'

describe('formatMs', () => {
  it('renders sub-second durations in ms', () => {
    expect(formatMs(340)).toBe('340ms')
  })
  it('renders durations over a second in seconds', () => {
    expect(formatMs(1500)).toBe('1.50s')
  })
})

describe('formatCell', () => {
  it('shows a placeholder for null', () => {
    expect(formatCell(null)).toBe('∅')
  })
  it('formats integers with thousands separators', () => {
    expect(formatCell(11472)).toBe('11,472')
  })
  it('appends the unit when given one', () => {
    expect(formatCell(11472.4, 'Mt')).toBe('11,472.4 Mt')
  })
  it('leaves year columns without thousands separators', () => {
    expect(formatCell(2015, undefined, 'year')).toBe('2015')
    expect(formatCell(2015, undefined, 'start_year')).toBe('2015')
    expect(formatCell(2015, undefined, 'population')).toBe('2,015')
  })
  it('passes strings through unchanged', () => {
    expect(formatCell('China')).toBe('China')
  })
  it('shows JSON values as JSON', () => {
    expect(formatCell({ name: 'Oslo', rank: 1 })).toBe('{"name":"Oslo","rank":1}')
    expect(formatCell(['a', 'b'])).toBe('["a","b"]')
  })
})

describe('formatRowCount', () => {
  it('uses the singular for exactly one row', () => {
    expect(formatRowCount(1)).toBe('1 row')
  })
  it('uses the plural otherwise', () => {
    expect(formatRowCount(0)).toBe('0 rows')
    expect(formatRowCount(42)).toBe('42 rows')
  })
})

describe('columnLabel', () => {
  it('appends the unit in parentheses when known', () => {
    expect(columnLabel('co2', { co2: 'Mt' })).toBe('co2 (Mt)')
  })
  it('falls back to the bare column name', () => {
    expect(columnLabel('country', {})).toBe('country')
  })
})

describe('columnDecimals', () => {
  it('uses the most precise value in the column, capped at 3', () => {
    expect(columnDecimals([[12172.009], [986.91], [5]], 0)).toBe(3)
    expect(columnDecimals([[1.5], [2.25]], 0)).toBe(2)
    expect(columnDecimals([[1], [null], ['x']], 0)).toBe(0)
    expect(columnDecimals([[1.123456]], 0)).toBe(3)
  })
  it('lines decimals up when passed to formatCell', () => {
    expect(formatCell(986.91, 'Mt', 'co2', 3)).toBe('986.910 Mt')
    expect(formatCell(5, undefined, 'co2', 2)).toBe('5.00')
  })
})
