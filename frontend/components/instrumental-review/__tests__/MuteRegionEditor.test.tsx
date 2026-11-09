import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MuteRegionEditor } from "../MuteRegionEditor"
import type { AudibleSegment } from "@/lib/api"

const defaultProps = {
  regions: [],
  audibleSegments: [] as AudibleSegment[],
  hasCustom: false,
  isCreatingCustom: false,
  onRemoveRegion: jest.fn(),
  onClearAll: jest.fn(),
  onCreateCustom: jest.fn(),
  onSeekTo: jest.fn(),
  onAddSegment: jest.fn(),
  onHoverRegion: jest.fn(),
  onHoverSegment: jest.fn(),
}

describe("MuteRegionEditor", () => {
  it("shows contextual help when segments exist but no regions", () => {
    const segments: AudibleSegment[] = [
      { start_seconds: 10, end_seconds: 12 },
      { start_seconds: 30, end_seconds: 35 },
    ]

    render(
      <MuteRegionEditor {...defaultProps} audibleSegments={segments} />
    )

    expect(screen.getByText(/lead vocal bleed/)).toBeInTheDocument()
    expect(screen.getByText(/custom mix/)).toBeInTheDocument()
  })

  it("shows clean recommendation when no segments detected", () => {
    render(<MuteRegionEditor {...defaultProps} />)

    expect(screen.getByText(/No backing vocals detected/)).toBeInTheDocument()
    expect(screen.getByText(/clean instrumental recommended/)).toBeInTheDocument()
  })

  it("shows shift+drag instruction", () => {
    const segments: AudibleSegment[] = [
      { start_seconds: 10, end_seconds: 12 },
    ]

    render(
      <MuteRegionEditor {...defaultProps} audibleSegments={segments} />
    )

    expect(screen.getByText(/drag on the waveform/)).toBeInTheDocument()
  })

  it('shows header as "Custom Mix" instead of "Mute Regions"', () => {
    render(<MuteRegionEditor {...defaultProps} />)

    expect(screen.getByText("Custom Mix")).toBeInTheDocument()
  })

  it("shows region count in header when regions exist", () => {
    render(
      <MuteRegionEditor
        {...defaultProps}
        regions={[
          { start_seconds: 10, end_seconds: 12 },
          { start_seconds: 30, end_seconds: 35 },
        ]}
      />
    )

    expect(screen.getByText("Custom Mix (2 muted)")).toBeInTheDocument()
  })

  it("calls onHoverRegion on mouse enter/leave of region tags", async () => {
    const onHoverRegion = jest.fn()
    const user = userEvent.setup()

    render(
      <MuteRegionEditor
        {...defaultProps}
        onHoverRegion={onHoverRegion}
        regions={[
          { start_seconds: 10, end_seconds: 12 },
        ]}
      />
    )

    const regionTag = screen.getByText("0:10 - 0:12").closest("div")!
    await user.hover(regionTag)
    expect(onHoverRegion).toHaveBeenCalledWith(0)

    await user.unhover(regionTag)
    expect(onHoverRegion).toHaveBeenCalledWith(null)
  })

  it("calls onHoverSegment on mouse enter/leave of segment buttons", async () => {
    const onHoverSegment = jest.fn()
    const user = userEvent.setup()
    const segments: AudibleSegment[] = [
      { start_seconds: 10, end_seconds: 12 },
    ]

    render(
      <MuteRegionEditor
        {...defaultProps}
        onHoverSegment={onHoverSegment}
        audibleSegments={segments}
      />
    )

    const segmentBtn = screen.getByText("0:10 - 0:12")
    await user.hover(segmentBtn)
    expect(onHoverSegment).toHaveBeenCalledWith(0)

    await user.unhover(segmentBtn)
    expect(onHoverSegment).toHaveBeenCalledWith(null)
  })
})
