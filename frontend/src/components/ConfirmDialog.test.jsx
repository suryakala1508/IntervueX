import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

function Harness({ onConfirm = vi.fn(), onCancel = vi.fn(), ...rest }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Open
      </button>
      <ConfirmDialog
        {...rest}
        open={open}
        onConfirm={() => {
          onConfirm()
          setOpen(false)
        }}
        onCancel={() => {
          onCancel()
          setOpen(false)
        }}
      />
    </div>
  )
}

async function openDialog(user) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <Harness
      onConfirm={onConfirm}
      onCancel={onCancel}
      title="Log out?"
      message="You'll need to sign in again to continue."
      confirmLabel="Log out"
      cancelLabel="Cancel"
      tone="danger"
    />,
  )
  await user.click(screen.getByRole('button', { name: 'Open' }))
  return { onConfirm, onCancel }
}

describe('ConfirmDialog', () => {
  it('renders a labelled modal when open', async () => {
    const user = userEvent.setup()
    await openDialog(user)

    const dialog = screen.getByRole('dialog', { name: 'Log out?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(screen.getByText(/sign in again to continue/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })

  it('renders nothing while closed', () => {
    const { container } = render(
      <ConfirmDialog open={false} title="Log out?" onConfirm={vi.fn()} onCancel={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('confirms and does not cancel', async () => {
    const user = userEvent.setup()
    const { onConfirm, onCancel } = await openDialog(user)

    await user.click(screen.getByRole('button', { name: 'Log out' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('cancels and does not confirm', async () => {
    const user = userEvent.setup()
    const { onConfirm } = await openDialog(user)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('closes on Escape', async () => {
    const user = userEvent.setup()
    await openDialog(user)

    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('closes when the backdrop is clicked', async () => {
    const user = userEvent.setup()
    await openDialog(user)

    await user.click(screen.getByRole('dialog'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('locks body scroll while open and restores it on close', async () => {
    const user = userEvent.setup()
    await openDialog(user)
    expect(document.body.style.overflow).toBe('hidden')

    await user.keyboard('{Escape}')
    expect(document.body.style.overflow).toBe('')
  })

  it('returns focus to the trigger once closed', async () => {
    const user = userEvent.setup()
    await openDialog(user)
    const trigger = screen.getByRole('button', { name: 'Open' })

    await user.keyboard('{Escape}')
    expect(trigger).toHaveFocus()
  })

  it('traps tab focus within the dialog', async () => {
    const user = userEvent.setup()
    await openDialog(user)

    await user.tab()
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Log out' })).toHaveFocus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
  })
})