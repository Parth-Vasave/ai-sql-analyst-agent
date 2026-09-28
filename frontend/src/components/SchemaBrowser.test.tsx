import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { ApiError, type DatabaseProfile } from '../api/types'
import { SchemaBrowser } from './SchemaBrowser'

vi.mock('../api/client')

const PROFILE: DatabaseProfile = {
  database_id: 'default',
  dialect: 'postgresql',
  sampling: 'safe',
  fingerprint: 'abc',
  tables: [
    {
      schema_name: 'public',
      name: 'co2_emissions',
      kind: 'table',
      comment: 'Yearly CO2 emissions.',
      estimated_rows: 45950,
      columns: [
        { name: 'country_id', type: 'INTEGER', nullable: false, comment: null, primary_key: true, sensitive: false, hints: null },
        {
          name: 'co2',
          type: 'NUMERIC',
          nullable: true,
          comment: 'Annual CO2, Mt.',
          primary_key: false,
          sensitive: false,
          hints: { null_fraction: 0.1, min: '0.0', max: '38598.578', categories: null, examples: null },
        },
      ],
    },
  ],
  relationships: [{ from_table: 'co2_emissions', from_columns: ['country_id'], to_table: 'countries', to_columns: ['id'], inferred: false }],
  notes: [],
}

describe('SchemaBrowser', () => {
  it('shows tables, columns and value ranges from the profile', async () => {
    vi.mocked(client.fetchProfile).mockResolvedValue(PROFILE)
    render(<SchemaBrowser databaseId="default" databaseName="Default database" onClose={vi.fn()} />)

    expect(await screen.findByText(/public\.co2_emissions/)).toBeInTheDocument()
    expect(screen.getByText(/45,950 rows/)).toBeInTheDocument()
    expect(screen.getByText('co2')).toBeInTheDocument()
    expect(screen.getByText(/0\.0–38598\.578/)).toBeInTheDocument()
    expect(screen.getByText(/co2_emissions\.country_id → countries\.id/)).toBeInTheDocument()
  })

  it('shows an error when the profile cannot be loaded', async () => {
    vi.mocked(client.fetchProfile).mockRejectedValue(new ApiError('Could not connect to the database.', 409))
    render(<SchemaBrowser databaseId="default" databaseName="Default database" onClose={vi.fn()} />)

    expect(await screen.findByText(/Could not connect to the database/)).toBeInTheDocument()
  })

  it('calls onClose', async () => {
    vi.mocked(client.fetchProfile).mockResolvedValue(PROFILE)
    const onClose = vi.fn()
    render(<SchemaBrowser databaseId="default" databaseName="Default database" onClose={onClose} />)
    await screen.findByText(/public\.co2_emissions/)

    await userEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
