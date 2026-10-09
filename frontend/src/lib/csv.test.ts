import { describe, expect, it } from 'vitest'
import { toCsv } from './csv'

describe('toCsv', () => {
  it('builds a header row and one row per data row', () => {
    expect(toCsv(['country', 'co2'], [['China', 11472.4], ['India', 2900]])).toBe(
      'country,co2\nChina,11472.4\nIndia,2900',
    )
  })

  it('quotes values containing commas, quotes or newlines', () => {
    expect(toCsv(['name'], [['Smith, John']])).toBe('name\n"Smith, John"')
    expect(toCsv(['name'], [['5"6"']])).toBe('name\n"5""6"""')
    expect(toCsv(['note'], [['line one\nline two']])).toBe('note\n"line one\nline two"')
  })

  it('renders null and undefined as empty cells', () => {
    expect(toCsv(['a', 'b'], [[null, undefined]])).toBe('a,b\n,')
  })

  it('writes JSON values as JSON', () => {
    expect(toCsv(['info'], [[{ name: 'Oslo' }], [[1, 2]]])).toBe('info\n"{""name"":""Oslo""}"\n"[1,2]"')
  })
})
