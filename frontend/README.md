# Karaoke Generator Frontend

Next.js frontend for the Karaoke Generator application.

## Quick Start

```bash
# Install dependencies
npm install

# Run development server
npm run dev
```

The app will be available at http://localhost:3000

## Development Setup

### Connecting to the Cloud Backend

In development, the frontend proxies API requests to the cloud backend (`api.nomadkaraoke.com`) via Next.js rewrites. This avoids CORS issues and allows local development without running a local backend.

The proxy is configured in `next.config.mjs`:
- All `/api/*` requests are forwarded to the cloud backend
- You can override the backend URL with `BACKEND_URL` environment variable

### Authentication

The backend requires authentication. To authenticate:

1. Create a `.env.local` file in the frontend directory:
   ```
   KARAOKE_ACCESS_TOKEN=your-token-here
   ```

2. The token is automatically loaded by Playwright tests
3. In the browser, the token is stored in `localStorage` as `karaoke_access_token`

## Testing

### Unit Tests (Jest)

```bash
# Run tests in watch mode
npm test

# Run tests with coverage
npm run test:coverage

# Run tests in CI mode
npm run test:ci
```

### E2E Tests (Playwright)

E2E tests run against the local dev server connected to the real cloud backend.

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI (interactive mode)
npm run test:e2e:ui

# Run in headed mode (see the browser)
npm run test:e2e:headed

# Run in debug mode
npm run test:e2e:debug
```

#### Authentication for E2E Tests

E2E tests require a valid access token. Set it in `.env.local`:

```
KARAOKE_ACCESS_TOKEN=your-token-here
```

The Playwright config (`playwright.config.ts`) automatically loads this file.

#### Test Structure

Tests are located in `e2e/`:

- `karaoke-generation.spec.ts` - Main test suite covering:
  - Homepage loading and form display
  - Search tab functionality
  - Audio search submission
  - Audio selection dialog flow
  - API health checks

#### Test Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│   Playwright    │────▶│  Next.js Dev     │────▶│  Cloud Backend      │
│   Browser       │     │  Server (:3000)  │     │  api.nomadkaraoke   │
└─────────────────┘     └──────────────────┘     └─────────────────────┘
                              │
                              ▼
                        API Proxy
                        /api/* → backend
```

#### Debugging Test Failures

1. **Screenshots**: Failed tests save screenshots to `test-results/`
2. **Videos**: First retry captures video (when retries enabled)
3. **Traces**: View detailed traces with `npx playwright show-trace <trace.zip>`
4. **HTML Report**: After running tests, view `npx playwright show-report`

#### Common Issues

- **401 Unauthorized**: Token missing or invalid - check `.env.local`
- **Socket hang up**: Backend operation taking too long - some operations (like audio download) can take minutes
- **Element outside viewport**: Dialog scrolling issues - tests use JavaScript click to handle this

## Project Structure

```
frontend/
├── app/                    # Next.js app router pages
├── components/             # React components
│   ├── ui/                 # shadcn/ui components
│   └── audio-search/       # Audio search feature components
├── lib/                    # Utilities and API client
│   └── api.ts              # Backend API client
├── e2e/                    # Playwright E2E tests
├── playwright.config.ts    # Playwright configuration
└── next.config.mjs         # Next.js configuration
```

## Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run start` | Start production server |
| `npm run lint` | Run ESLint |
| `npm test` | Run unit tests (watch mode) |
| `npm run test:ci` | Run unit tests (CI mode with coverage) |
| `npm run test:e2e` | Run E2E tests |
| `npm run test:e2e:ui` | Run E2E tests with interactive UI |
