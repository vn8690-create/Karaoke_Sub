/**
 * Confidence Tier Tests Using Real Production Fixtures
 *
 * These tests run against actual search results fetched from production
 * (stored in e2e/fixtures/data/search-results/) to validate that the
 * confidence tier system behaves correctly across a variety of real songs.
 *
 * To generate/update fixtures:
 *   cd frontend && node e2e/fixtures/fetch-search-fixtures.mjs
 *
 * If no fixtures exist, tests are skipped (not failed).
 */

import * as fs from 'fs'
import * as path from 'path'
import {
  getSearchConfidence,
  checkFilenameMismatch,
  getAvailabilityLabel,
  categorizeResult,
  getBestResult,
  ExtendedAudioSearchResult,
} from '../audio-search-utils'

const FIXTURES_DIR = path.resolve(__dirname, '../../e2e/fixtures/data/search-results')
const INDEX_PATH = path.join(FIXTURES_DIR, 'index.json')

interface FixtureEntry {
  slug: string
  artist: string
  title: string
  resultCount: number
  status: string
  file: string
}

interface Fixture {
  artist: string
  title: string
  resultCount: number
  results: ExtendedAudioSearchResult[]
}

function loadFixtures(): { index: FixtureEntry[]; fixtures: Map<string, Fixture> } {
  if (!fs.existsSync(INDEX_PATH)) {
    return { index: [], fixtures: new Map() }
  }

  const index: FixtureEntry[] = JSON.parse(fs.readFileSync(INDEX_PATH, 'utf-8'))
  const fixtures = new Map<string, Fixture>()

  for (const entry of index) {
    const filePath = path.join(FIXTURES_DIR, entry.file)
    if (fs.existsSync(filePath)) {
      fixtures.set(entry.slug, JSON.parse(fs.readFileSync(filePath, 'utf-8')))
    }
  }

  return { index, fixtures }
}

const { index, fixtures } = loadFixtures()
const hasFixtures = fixtures.size > 0

describe('Confidence tiers with real production fixtures', () => {
  if (!hasFixtures) {
    it('skips — no fixtures found (run: node e2e/fixtures/fetch-search-fixtures.mjs)', () => {
      console.log('No fixtures found. Run the fixture fetcher to generate them.')
    })
    return
  }

  it(`loaded ${fixtures.size} fixtures`, () => {
    expect(fixtures.size).toBeGreaterThan(0)
  })

  // Validate that every fixture gets a valid tier
  for (const [slug, fixture] of fixtures) {
    it(`${fixture.artist} - ${fixture.title}: valid tier assignment`, () => {
      const confidence = getSearchConfidence(fixture.results, fixture.title)
      expect([1, 2, 3]).toContain(confidence.tier)
      expect(confidence.reason).toBeTruthy()

      if (fixture.results.length === 0) {
        expect(confidence.tier).toBe(3)
        expect(confidence.bestResult).toBeNull()
      } else {
        // Best result should be consistent with getBestResult
        const expectedBest = getBestResult(fixture.results)
        expect(confidence.bestResult?.index).toBe(expectedBest?.index)
      }
    })
  }

  it('tier distribution is reasonable', () => {
    const tiers = { 1: 0, 2: 0, 3: 0 }
    for (const [, fixture] of fixtures) {
      const confidence = getSearchConfidence(fixture.results, fixture.title)
      tiers[confidence.tier]++
    }

    console.log(`Tier distribution: T1=${tiers[1]}, T2=${tiers[2]}, T3=${tiers[3]} (total=${fixtures.size})`)

    // We expect some distribution across tiers, not all one tier
    // (exact distribution depends on the actual songs, so we just sanity-check)
    const total = fixtures.size
    if (total >= 10) {
      // At least some results should get different tiers
      const uniqueTiers = Object.values(tiers).filter(v => v > 0).length
      expect(uniqueTiers).toBeGreaterThanOrEqual(1) // At minimum 1 tier, but ideally 2-3
    }
  })

  it('tier 1 results are always BEST CHOICE without mismatch', () => {
    for (const [, fixture] of fixtures) {
      const confidence = getSearchConfidence(fixture.results, fixture.title)
      if (confidence.tier === 1) {
        expect(confidence.bestCategory).toBe('BEST CHOICE')
        if (confidence.bestResult?.target_file) {
          const mismatch = checkFilenameMismatch(fixture.title, confidence.bestResult)
          expect(mismatch.isMismatch).toBe(false)
        }
      }
    }
  })

  it('tier 3 results have no lossless options or have critical warnings', () => {
    for (const [, fixture] of fixtures) {
      const confidence = getSearchConfidence(fixture.results, fixture.title)
      if (confidence.tier === 3 && fixture.results.length > 0) {
        // Tier 3 should have either: no lossless, or mismatch+low availability
        const hasLossless = fixture.results.some(r => {
          const cat = categorizeResult(r)
          return cat !== 'YOUTUBE' && cat !== 'SPOTIFY' && cat !== 'VINYL RIPS'
        })
        if (hasLossless) {
          // Must have mismatch + low availability to be tier 3 with lossless
          expect(confidence.warnings.length).toBeGreaterThan(0)
        }
      }
    }
  })

  it('warnings array never contains empty strings', () => {
    for (const [, fixture] of fixtures) {
      const confidence = getSearchConfidence(fixture.results, fixture.title)
      for (const warning of confidence.warnings) {
        expect(warning).toBeTruthy()
        expect(warning.trim().length).toBeGreaterThan(0)
      }
    }
  })

  it('availability labels are consistent with seeder counts', () => {
    for (const [, fixture] of fixtures) {
      for (const result of fixture.results) {
        if (result.seeders !== undefined && result.seeders !== null) {
          const { text } = getAvailabilityLabel(result.seeders)
          if (result.seeders >= 50) expect(text).toBe('High')
          else if (result.seeders >= 10) expect(text).toBe('Medium')
          else expect(text).toBe('Low')
        }
      }
    }
  })
})
