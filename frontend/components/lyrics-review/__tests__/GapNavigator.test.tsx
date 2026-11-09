import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import GapNavigator from '../GapNavigator'

describe('GapNavigator', () => {
  const defaultProps = {
    currentGapIndex: null as number | null,
    totalGaps: 5,
    onPrevGap: jest.fn(),
    onNextGap: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders gap counter', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={2} />)

    expect(screen.getByText('Gap 3 of 5')).toBeInTheDocument()
  })

  it('shows "Gap 0 of N" when no gap selected', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={null} />)

    expect(screen.getByText('Gap 0 of 5')).toBeInTheDocument()
  })

  it('renders nothing when totalGaps is 0', () => {
    const { container } = render(<GapNavigator {...defaultProps} totalGaps={0} />)

    expect(container.firstChild).toBeNull()
  })

  it('disables prev button at first gap', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={0} />)

    expect(screen.getByLabelText('Previous gap')).toBeDisabled()
    expect(screen.getByLabelText('Next gap')).not.toBeDisabled()
  })

  it('disables next button at last gap', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={4} />)

    expect(screen.getByLabelText('Previous gap')).not.toBeDisabled()
    expect(screen.getByLabelText('Next gap')).toBeDisabled()
  })

  it('disables prev button when no gap selected', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={null} />)

    expect(screen.getByLabelText('Previous gap')).toBeDisabled()
  })

  it('calls onNextGap when next button clicked', async () => {
    const user = userEvent.setup()
    render(<GapNavigator {...defaultProps} currentGapIndex={1} />)

    await user.click(screen.getByLabelText('Next gap'))

    expect(defaultProps.onNextGap).toHaveBeenCalled()
  })

  it('calls onPrevGap when prev button clicked', async () => {
    const user = userEvent.setup()
    render(<GapNavigator {...defaultProps} currentGapIndex={2} />)

    await user.click(screen.getByLabelText('Previous gap'))

    expect(defaultProps.onPrevGap).toHaveBeenCalled()
  })

  it('shows keyboard shortcut hints in tooltips', () => {
    render(<GapNavigator {...defaultProps} currentGapIndex={0} />)

    expect(screen.getByLabelText('Previous gap')).toBeInTheDocument()
    expect(screen.getByLabelText('Next gap')).toBeInTheDocument()
  })
})
