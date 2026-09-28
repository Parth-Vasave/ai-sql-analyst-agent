import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import * as client from '../api/client'
import { ApiError, type LlmKeyStatus } from '../api/types'
import { LlmKeyForm } from './LlmKeyForm'

vi.mock('../api/client')

const UNCONFIGURED: LlmKeyStatus = {
  configured: false,
  source: 'none',
  model: 'gemini-3.8-flash',
  base_url: 'https://generativelanguage.googleapis.com/v1beta/openai/',
}

describe('LlmKeyForm', () => {
  it('shows the current status and lets the user set a key', async () => {
    vi.mocked(client.fetchLlmKeyStatus).mockResolvedValue(UNCONFIGURED)
    const configured: LlmKeyStatus = { ...UNCONFIGURED, configured: true, source: 'ui' }
    vi.mocked(client.setLlmKey).mockResolvedValue(configured)
    render(<LlmKeyForm onClose={vi.fn()} />)

    expect(await screen.findByText(/not configured/i)).toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/api key/i), '  my-secret-key  ')
    await userEvent.click(screen.getByRole('button', { name: /^set key$/i }))

    expect(client.setLlmKey).toHaveBeenCalledWith('my-secret-key')
    expect(await screen.findByText(/set through this ui/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/api key/i)).toHaveValue('')
  })

  it('lets the user remove a configured key', async () => {
    const configured: LlmKeyStatus = { ...UNCONFIGURED, configured: true, source: 'ui' }
    vi.mocked(client.fetchLlmKeyStatus).mockResolvedValueOnce(configured).mockResolvedValue(UNCONFIGURED)
    vi.mocked(client.removeLlmKey).mockResolvedValue(undefined)
    render(<LlmKeyForm onClose={vi.fn()} />)

    await screen.findByRole('button', { name: /remove key/i })
    await userEvent.click(screen.getByRole('button', { name: /remove key/i }))

    expect(client.removeLlmKey).toHaveBeenCalled()
    expect(await screen.findByText(/not configured/i)).toBeInTheDocument()
  })

  it('shows an error when setting the key is disabled', async () => {
    vi.mocked(client.fetchLlmKeyStatus).mockResolvedValue(UNCONFIGURED)
    vi.mocked(client.setLlmKey).mockRejectedValue(
      new ApiError('Setting the LLM key from the UI is disabled. Set ALLOW_UI_LLM_KEY=true (local use only).', 403),
    )
    render(<LlmKeyForm onClose={vi.fn()} />)
    await screen.findByText(/not configured/i)

    await userEvent.type(screen.getByLabelText(/api key/i), 'my-secret-key')
    await userEvent.click(screen.getByRole('button', { name: /^set key$/i }))

    expect(await screen.findByText(/ALLOW_UI_LLM_KEY/)).toBeInTheDocument()
  })

  it('never renders the typed key outside the input', async () => {
    vi.mocked(client.fetchLlmKeyStatus).mockResolvedValue(UNCONFIGURED)
    render(<LlmKeyForm onClose={vi.fn()} />)
    await screen.findByText(/not configured/i)

    await userEvent.type(screen.getByLabelText(/api key/i), 'super-secret-value')

    expect(screen.getByLabelText(/api key/i)).toHaveAttribute('type', 'password')
    expect(document.body.textContent).not.toContain('super-secret-value')
  })
})
