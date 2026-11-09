import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import EditFeedbackBar from '../EditFeedbackBar'
import type { EditLogEntry } from '@/lib/lyrics-review/types'

function makeEntry(overrides: Partial<EditLogEntry> = {}): EditLogEntry {
  return {
    id: 'entry-1',
    timestamp: new Date().toISOString(),
    operation: 'word_change',
    segment_id: 's1',
    segment_index: 0,
    word_ids_before: ['w1'],
    word_ids_after: ['w1'],
    text_before: 'helo',
    text_after: 'hello',
    feedback: null,
    ...overrides,
  }
}

describe('EditFeedbackBar', () => {
  beforeEach(() => {
    jest.useFakeTimers()
  })

  afterEach(() => {
    jest.useRealTimers()
  })

  it('renders nothing when not visible', () => {
    const { container } = render(
      <EditFeedbackBar entry={makeEntry()} visible={false} onFeedback={jest.fn()} onDismiss={jest.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when entry is null', () => {
    const { container } = render(
      <EditFeedbackBar entry={null} visible={true} onFeedback={jest.fn()} onDismiss={jest.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows question text for word_change', () => {
    render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={jest.fn()} onDismiss={jest.fn()} />
    )
    expect(screen.getByText(/Changed "helo" → "hello", why\?/)).toBeInTheDocument()
  })

  it('shows question text for word_delete', () => {
    render(
      <EditFeedbackBar
        entry={makeEntry({ operation: 'word_delete', text_before: 'ghost', text_after: '' })}
        visible={true}
        onFeedback={jest.fn()}
        onDismiss={jest.fn()}
      />
    )
    expect(screen.getByText(/Removed "ghost", why\?/)).toBeInTheDocument()
  })

  it('shows question text for word_add', () => {
    render(
      <EditFeedbackBar
        entry={makeEntry({ operation: 'word_add', text_before: '', text_after: 'world' })}
        visible={true}
        onFeedback={jest.fn()}
        onDismiss={jest.fn()}
      />
    )
    expect(screen.getByText(/Added "world", why\?/)).toBeInTheDocument()
  })

  it('shows correct reason buttons for word_change', () => {
    render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={jest.fn()} onDismiss={jest.fn()} />
    )
    expect(screen.getByText('Mis-heard word')).toBeInTheDocument()
    expect(screen.getByText('Wrong lyrics')).toBeInTheDocument()
    expect(screen.getByText('Spelling/punctuation')).toBeInTheDocument()
    expect(screen.getByText('Other')).toBeInTheDocument()
  })

  it('shows correct reason buttons for word_delete', () => {
    render(
      <EditFeedbackBar
        entry={makeEntry({ operation: 'word_delete' })}
        visible={true}
        onFeedback={jest.fn()}
        onDismiss={jest.fn()}
      />
    )
    expect(screen.getByText('Phantom word')).toBeInTheDocument()
    expect(screen.getByText('Duplicate')).toBeInTheDocument()
  })

  it('shows correct reason buttons for word_add', () => {
    render(
      <EditFeedbackBar
        entry={makeEntry({ operation: 'word_add' })}
        visible={true}
        onFeedback={jest.fn()}
        onDismiss={jest.fn()}
      />
    )
    expect(screen.getByText('Missing word')).toBeInTheDocument()
    expect(screen.getByText('Split word')).toBeInTheDocument()
  })

  it('calls onFeedback with correct reason when button clicked', async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime })
    const onFeedback = jest.fn()
    const onDismiss = jest.fn()

    render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={onFeedback} onDismiss={onDismiss} />
    )

    await user.click(screen.getByText('Mis-heard word'))
    expect(onFeedback).toHaveBeenCalledWith('entry-1', 'misheard_word')
    expect(onDismiss).toHaveBeenCalled()
  })

  it('calls onFeedback with no_response and onDismiss when X clicked', async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime })
    const onFeedback = jest.fn()
    const onDismiss = jest.fn()

    render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={onFeedback} onDismiss={onDismiss} />
    )

    // Click the X button (last button)
    const buttons = screen.getAllByRole('button')
    const closeButton = buttons[buttons.length - 1]
    await user.click(closeButton)

    expect(onFeedback).toHaveBeenCalledWith('entry-1', 'no_response')
    expect(onDismiss).toHaveBeenCalled()
  })

  it('auto-dismisses after 10 seconds with no_response', () => {
    const onFeedback = jest.fn()
    const onDismiss = jest.fn()

    render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={onFeedback} onDismiss={onDismiss} />
    )

    expect(onFeedback).not.toHaveBeenCalled()

    act(() => {
      jest.advanceTimersByTime(10_000)
    })

    expect(onFeedback).toHaveBeenCalledWith('entry-1', 'no_response')
    expect(onDismiss).toHaveBeenCalled()
  })

  it('pauses auto-dismiss while hovered', async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime })
    const onFeedback = jest.fn()
    const onDismiss = jest.fn()

    const { container } = render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={onFeedback} onDismiss={onDismiss} />
    )

    const bar = container.firstChild as HTMLElement

    // Advance 6 seconds, then hover
    act(() => {
      jest.advanceTimersByTime(6_000)
    })
    expect(onFeedback).not.toHaveBeenCalled()

    await user.hover(bar)

    // Advance well past 10s total — should NOT dismiss while hovered
    act(() => {
      jest.advanceTimersByTime(10_000)
    })
    expect(onFeedback).not.toHaveBeenCalled()

    // Unhover — timer resumes with remaining ~4s
    await user.unhover(bar)

    // 3s after unhover — still not dismissed
    act(() => {
      jest.advanceTimersByTime(3_000)
    })
    expect(onFeedback).not.toHaveBeenCalled()

    // 2 more seconds (past the remaining ~4s) — should dismiss
    act(() => {
      jest.advanceTimersByTime(2_000)
    })
    expect(onFeedback).toHaveBeenCalledWith('entry-1', 'no_response')
    expect(onDismiss).toHaveBeenCalled()
  })

  it('does not auto-dismiss if user clicks a reason while hovered', async () => {
    const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime })
    const onFeedback = jest.fn()
    const onDismiss = jest.fn()

    const { container } = render(
      <EditFeedbackBar entry={makeEntry()} visible={true} onFeedback={onFeedback} onDismiss={onDismiss} />
    )

    const bar = container.firstChild as HTMLElement

    await user.hover(bar)
    await user.click(screen.getByText('Mis-heard word'))

    expect(onFeedback).toHaveBeenCalledWith('entry-1', 'misheard_word')
    expect(onDismiss).toHaveBeenCalled()

    // Advancing time should not trigger a second no_response call
    onFeedback.mockClear()
    onDismiss.mockClear()

    act(() => {
      jest.advanceTimersByTime(15_000)
    })
    expect(onFeedback).not.toHaveBeenCalled()
  })
})
