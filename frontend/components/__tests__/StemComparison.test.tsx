/**
 * Tests for StemComparison component
 *
 * This component renders audio type selection tabs for the instrumental review UI.
 * It supports showing a loading spinner when audio is loading.
 */

import { render, screen, fireEvent } from '@testing-library/react'
import { StemComparison, AudioType } from '../instrumental-review/StemComparison'

describe('StemComparison', () => {
  const mockOnAudioChange = jest.fn()

  const defaultProps = {
    activeAudio: 'clean' as AudioType,
    onAudioChange: mockOnAudioChange,
    hasOriginal: true,
    hasWithBacking: true,
    hasCustom: false,
    hasUploaded: false,
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders available audio options', () => {
    render(<StemComparison {...defaultProps} />)

    expect(screen.getByText('Original')).toBeInTheDocument()
    expect(screen.getByText('Backing Vocals Only')).toBeInTheDocument()
    expect(screen.getByText('Pure Instrumental')).toBeInTheDocument()
    expect(screen.getByText('Instrumental + Backing')).toBeInTheDocument()
  })

  it('does not render unavailable options', () => {
    render(<StemComparison {...defaultProps} hasOriginal={false} hasWithBacking={false} />)

    expect(screen.queryByText('Original')).not.toBeInTheDocument()
    expect(screen.queryByText('Instrumental + Backing')).not.toBeInTheDocument()
    // These are always available
    expect(screen.getByText('Backing Vocals Only')).toBeInTheDocument()
    expect(screen.getByText('Pure Instrumental')).toBeInTheDocument()
  })

  it('shows custom option when available', () => {
    render(<StemComparison {...defaultProps} hasCustom={true} />)

    expect(screen.getByText('Custom')).toBeInTheDocument()
  })

  it('shows uploaded option when available', () => {
    render(<StemComparison {...defaultProps} hasUploaded={true} uploadedFilename="my-instrumental.flac" />)

    const uploadedButton = screen.getByText('Uploaded')
    expect(uploadedButton).toBeInTheDocument()
    expect(uploadedButton).toHaveAttribute('title', 'my-instrumental.flac')
  })

  it('calls onAudioChange when an option is clicked', () => {
    render(<StemComparison {...defaultProps} />)

    fireEvent.click(screen.getByText('Original'))
    expect(mockOnAudioChange).toHaveBeenCalledWith('original')

    fireEvent.click(screen.getByText('Backing Vocals Only'))
    expect(mockOnAudioChange).toHaveBeenCalledWith('backing')
  })

  it('highlights the active audio option', () => {
    render(<StemComparison {...defaultProps} activeAudio="backing" />)

    const backingButton = screen.getByText('Backing Vocals Only')
    expect(backingButton).toHaveClass('bg-primary')
  })

  describe('loading state', () => {
    it('shows loading spinner on active tab when isLoading is true', () => {
      render(<StemComparison {...defaultProps} activeAudio="backing" isLoading={true} />)

      // The Loader2 icon should be present in the active tab
      const backingButton = screen.getByText('Backing Vocals Only').closest('button')
      expect(backingButton).toContainHTML('animate-spin')
    })

    it('does not show spinner on inactive tabs when loading', () => {
      render(<StemComparison {...defaultProps} activeAudio="backing" isLoading={true} />)

      const originalButton = screen.getByText('Original').closest('button')
      expect(originalButton).not.toContainHTML('animate-spin')
    })

    it('disables all tabs when loading', () => {
      render(<StemComparison {...defaultProps} isLoading={true} />)

      const originalButton = screen.getByText('Original').closest('button')
      const backingButton = screen.getByText('Backing Vocals Only').closest('button')

      expect(originalButton).toBeDisabled()
      expect(backingButton).toBeDisabled()
    })

    it('does not disable tabs when not loading', () => {
      render(<StemComparison {...defaultProps} isLoading={false} />)

      const originalButton = screen.getByText('Original').closest('button')
      expect(originalButton).not.toBeDisabled()
    })

    it('applies opacity styling to inactive tabs when loading', () => {
      render(<StemComparison {...defaultProps} activeAudio="backing" isLoading={true} />)

      const originalButton = screen.getByText('Original').closest('button')
      expect(originalButton).toHaveClass('opacity-50')
    })
  })
})
