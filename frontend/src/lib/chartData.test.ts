import { describe, expect, it } from 'vitest'
import { pivotBySeries, statValue, toRecords } from './chartData'
import type { ChartSpec } from '../api/types'

describe('toRecords', () => {
  it('zips columns and row values into objects', () => {
    expect(toRecords(['country', 'co2'], [['China', 100], ['India', 50]])).toEqual([
      { country: 'China', co2: 100 },
      { country: 'India', co2: 50 },
    ])
  })
})

describe('pivotBySeries', () => {
  it('groups rows by x, one key per series value', () => {
    const records = toRecords(
      ['year', 'country', 'co2'],
      [
        [2020, 'China', 100],
        [2020, 'India', 50],
        [2021, 'China', 110],
        [2021, 'India', 55],
      ],
    )
    const { data, seriesKeys } = pivotBySeries(records, 'year', 'co2', 'country')
    expect(seriesKeys).toEqual(['China', 'India'])
    expect(data).toEqual([
      { year: 2020, China: 100, India: 50 },
      { year: 2021, China: 110, India: 55 },
    ])
  })
})

describe('statValue', () => {
  it('reads the named measure and label column from the first row', () => {
    const spec: ChartSpec = { type: 'stat', x: null, y: ['co2'], series: null, label: 'country', orientation: null, reason: 'single value' }
    const result = statValue(spec, ['country', 'co2'], [['China', 11472.4]])
    expect(result).toEqual({ value: 11472.4, label: 'China' })
  })
  it('falls back to the column name when there is no label column', () => {
    const spec: ChartSpec = { type: 'stat', x: null, y: ['co2'], series: null, label: null, orientation: null, reason: 'single value' }
    const result = statValue(spec, ['co2'], [[11472.4]])
    expect(result).toEqual({ value: 11472.4, label: 'co2' })
  })
})
