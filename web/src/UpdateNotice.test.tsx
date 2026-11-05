import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import UpdateNotice from './UpdateNotice'
import { UPDATE_READY_EVENT } from './pwa'

test('offers a refresh only once a new version is ready, and can be dismissed', async () => {
  render(<UpdateNotice />)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  act(() => { window.dispatchEvent(new Event(UPDATE_READY_EVENT)) })
  expect(screen.getByRole('status')).toHaveTextContent('A new version of PETAdvice is ready.')
  expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Dismiss' }))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})
