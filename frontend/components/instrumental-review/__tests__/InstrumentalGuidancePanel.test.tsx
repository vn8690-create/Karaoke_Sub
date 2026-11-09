import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { InstrumentalGuidancePanel } from "../InstrumentalGuidancePanel"
import type { BackingVocalAnalysis, AudibleSegment } from "@/lib/api"

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: jest.fn((key: string) => store[key] || null),
    setItem: jest.fn((key: string, value: string) => {
      store[key] = value
    }),
    removeItem: jest.fn((key: string) => {
      delete store[key]
    }),
    clear: jest.fn(() => {
      store = {}
    }),
  }
})()
Object.defineProperty(window, "localStorage", { value: localStorageMock })

const makeAnalysis = (
  overrides: Partial<BackingVocalAnalysis> = {}
): BackingVocalAnalysis => ({
  audible_segments: [],
  audible_percentage: 4,
  recommended_selection: "clean",
  ...overrides,
})

const makeSegments = (count: number): AudibleSegment[] =>
  Array.from({ length: count }, (_, i) => ({
    start_seconds: i * 10,
    end_seconds: i * 10 + 2,
  }))

describe("InstrumentalGuidancePanel", () => {
  beforeEach(() => {
    localStorageMock.clear()
    jest.clearAllMocks()
  })

  describe("simple case - clean recommended with low backing vocals", () => {
    it("shows simplified guidance when clean recommended and < 10% backing vocals", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({ audible_percentage: 4, recommended_selection: "clean" })}
          audibleSegments={[]}
        />
      )

      expect(screen.getByText(/Choose your karaoke backing track/)).toBeInTheDocument()
      expect(screen.getByText(/very little backing vocal content/)).toBeInTheDocument()
      expect(screen.getByText(/Clean Instrumental/)).toBeInTheDocument()
    })

    it("shows the backing vocal percentage", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({ audible_percentage: 4 })}
          audibleSegments={[]}
        />
      )

      expect(screen.getByText(/4%/)).toBeInTheDocument()
    })
  })

  describe("complex case - backing vocals need review", () => {
    it("shows full workflow steps when backing vocals are significant", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({
            audible_percentage: 25,
            recommended_selection: "with_backing",
          })}
          audibleSegments={makeSegments(5)}
        />
      )

      expect(screen.getByText(/Step 1:/)).toBeInTheDocument()
      expect(screen.getByText(/Step 2:/)).toBeInTheDocument()
      expect(screen.getByText(/Step 3/)).toBeInTheDocument()
    })

    it("shows segment count in step 1", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({
            audible_percentage: 25,
            recommended_selection: "with_backing",
          })}
          audibleSegments={makeSegments(3)}
        />
      )

      expect(screen.getByText(/3 detected/)).toBeInTheDocument()
    })

    it("explains what backing vocals are", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({
            audible_percentage: 25,
            recommended_selection: "with_backing",
          })}
          audibleSegments={makeSegments(2)}
        />
      )

      expect(screen.getByText(/harmony\/chorus voices/)).toBeInTheDocument()
    })

    it("shows full steps when clean recommended but >= 10% backing vocals", () => {
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis({
            audible_percentage: 15,
            recommended_selection: "clean",
          })}
          audibleSegments={makeSegments(3)}
        />
      )

      expect(screen.getByText(/Step 1:/)).toBeInTheDocument()
      expect(screen.getByText(/Step 2:/)).toBeInTheDocument()
    })
  })

  describe("dismissal and persistence", () => {
    it("dismisses tip and stores in localStorage", async () => {
      const user = userEvent.setup()
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis()}
          audibleSegments={[]}
        />
      )

      await user.click(screen.getByLabelText("Dismiss tip"))

      expect(localStorageMock.setItem).toHaveBeenCalledWith(
        "instrumentalReviewGuidanceDismissed",
        "true"
      )
      expect(screen.queryByText(/Choose your karaoke backing track/)).not.toBeInTheDocument()
    })

    it('shows "Show tips" link after dismissal', async () => {
      const user = userEvent.setup()
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis()}
          audibleSegments={[]}
        />
      )

      await user.click(screen.getByLabelText("Dismiss tip"))
      expect(screen.getByText("Show tips")).toBeInTheDocument()
    })

    it('restores tip when "Show tips" is clicked', async () => {
      const user = userEvent.setup()
      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis()}
          audibleSegments={[]}
        />
      )

      await user.click(screen.getByLabelText("Dismiss tip"))
      await user.click(screen.getByText("Show tips"))

      expect(screen.getByText(/Choose your karaoke backing track/)).toBeInTheDocument()
      expect(localStorageMock.removeItem).toHaveBeenCalledWith(
        "instrumentalReviewGuidanceDismissed"
      )
    })

    it("starts dismissed if localStorage has been set", () => {
      localStorageMock.getItem.mockReturnValueOnce("true")

      render(
        <InstrumentalGuidancePanel
          analysis={makeAnalysis()}
          audibleSegments={[]}
        />
      )

      expect(screen.queryByText(/Choose your karaoke backing track/)).not.toBeInTheDocument()
      expect(screen.getByText("Show tips")).toBeInTheDocument()
    })
  })
})
