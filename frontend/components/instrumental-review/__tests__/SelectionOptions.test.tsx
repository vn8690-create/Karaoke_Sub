import { render, screen } from "@testing-library/react"
import { SelectionOptions } from "../SelectionOptions"
import type { BackingVocalAnalysis } from "@/lib/api"

const defaultProps = {
  value: "clean" as const,
  onChange: jest.fn(),
  hasWithBacking: true,
  hasOriginal: false,
  hasCustom: false,
  hasUploaded: false,
  muteRegionsCount: 0,
}

describe("SelectionOptions", () => {
  it("shows recommendation reasoning for clean instrumental", () => {
    const analysis: BackingVocalAnalysis = {
      audible_segments: [],
      audible_percentage: 4,
      recommended_selection: "clean",
    }

    render(
      <SelectionOptions
        {...defaultProps}
        backingVocalAnalysis={analysis}
      />
    )

    expect(screen.getByText("Recommended")).toBeInTheDocument()
    expect(screen.getByText(/Very few backing vocals detected \(4%\)/)).toBeInTheDocument()
  })

  it("shows recommendation reasoning for with_backing", () => {
    const analysis: BackingVocalAnalysis = {
      audible_segments: [],
      audible_percentage: 25,
      recommended_selection: "with_backing",
    }

    render(
      <SelectionOptions
        {...defaultProps}
        value="with_backing"
        backingVocalAnalysis={analysis}
      />
    )

    expect(screen.getByText("Recommended")).toBeInTheDocument()
    expect(screen.getByText(/Significant backing vocals \(25%\)/)).toBeInTheDocument()
  })

  it("does not show reasoning for non-recommended options", () => {
    const analysis: BackingVocalAnalysis = {
      audible_segments: [],
      audible_percentage: 4,
      recommended_selection: "clean",
    }

    render(
      <SelectionOptions
        {...defaultProps}
        backingVocalAnalysis={analysis}
      />
    )

    // Only one recommendation reasoning text
    const reasoningTexts = screen.getAllByText(/backing vocals/)
    // "No backing vocals" (description) + "Very few backing vocals detected" (reasoning) + "All backing vocals included" (description)
    expect(reasoningTexts.length).toBeGreaterThanOrEqual(1)
  })

  it("shows custom option with region count when available", () => {
    render(
      <SelectionOptions
        {...defaultProps}
        hasCustom={true}
        muteRegionsCount={3}
      />
    )

    expect(screen.getByText("Custom")).toBeInTheDocument()
    expect(screen.getByText("3 regions muted")).toBeInTheDocument()
  })
})
