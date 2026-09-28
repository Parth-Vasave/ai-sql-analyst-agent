import { describe, expect, it } from 'vitest'
import { columnLabel, formatCell, formatMs, formatRowCount } from './format'

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
  it('passes strings through unchanged', () => {
    expect(formatCell('China')).toBe('China')
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
