# Agent Instructions: Nomad Karaoke E2E Production Testing

## Context

You are acting on behalf of Andrew, the creator of Nomad Karaoke, who is building a fully functional end-to-end karaoke video generation platform. The platform has two modes:

1. **Local CLI** (`karaoke-gen`) - For power users running locally
2. **Public Web Service** (`gen.nomadkaraoke.com`) - For paying customers ($5/track via Stripe)

## Current State

The platform has been under heavy development with many features implemented, but **end-to-end functionality for real users on gen.nomadkaraoke.com is not fully working yet**. The goal is to make the complete user journey functional in production.

## Business Model (Planned)

- **buy.nomadkaraoke.com** - Customer intro/landing page with Stripe payment flow
- Payment generates a single-use token
- Customer is redirected to **gen.nomadkaraoke.com** with token ready to use
- Each track costs $5

## Your Primary Mission

**Test and fix the production system until end-to-end karaoke generation works reliably.**

### The Complete User Journey to Test

1. **Input** - User enters artist name and song title
2. **Audio Selection** - User selects audio source
3. **Download & Preparation** - System downloads and prepares audio (wait for completion)
4. **Lyrics Review** - User reviews/corrects lyrics in the web UI
5. **Preview Video** - Wait for preview video to load
6. **Submit Review** - User submits corrected lyrics
7. **Render Stage** - Wait for render to complete
8. **Instrumental Selection** - User selects instrumental via web UI
9. **Final Render & Distribution** - Wait for final render and distribution
10. **Verification** - Click to view uploaded YouTube video
11. **Verification** - Click Dropbox folder link to view shared folder

## Your Working Process

Use Playwright to automate and test this journey against **live production** at `gen.nomadkaraoke.com`.

### The Fix Loop

When you encounter something broken:

1. **Investigate** - Understand the root cause
2. **Fix** - Implement the fix
3. **Improve Tests** - Add/update tests to cover the issue
4. **Refactor** - Clean up if necessary
5. **PR** - Create a pull request with clear description
6. **CI** - Ensure all checks pass
7. **Merge** - Merge the PR
8. **Deploy** - Wait for deployment to complete
9. **Retest** - Test again in production
10. **Repeat** - Continue until everything works

## Key Rules

### From CLAUDE.md (Must Follow)

- **Never commit directly to `main`** - Always use feature branches
- **Always run tests before committing** - `make test` for backend, `cd frontend && npm run test:all` for frontend
- **Bump version** in `pyproject.toml` for every commit
- **Use git worktrees** for non-trivial changes
- **Infrastructure changes** must go through Pulumi IaC

### Testing Commands

```bash
# Backend tests (10 min timeout, limit output)
make test 2>&1 | tail -n 500

# Frontend tests
cd frontend && npm run test:all 2>&1 | tail -n 200
```

### Pre-commit Checklist

- [ ] Tests pass
- [ ] Version bumped in `pyproject.toml`
- [ ] PR created with clear description
- [ ] CI checks pass before merge

## Permissions

You have permission to:

- Run any command necessary
- Use Playwright to interact with browsers
- Make changes to any part of the codebase
- Create PRs and merge them (after CI passes)
- Test against live production

## Success Criteria

The mission is complete when:

1. Any artist/title can be entered on gen.nomadkaraoke.com
2. The full generation process completes successfully
3. A karaoke video is uploaded to YouTube
4. Files are distributed to Dropbox
5. The entire flow is covered by automated E2E tests

## Key URLs

- **Production Frontend**: https://gen.nomadkaraoke.com
- **Production API**: https://api.nomadkaraoke.com (inferred from README)
- **Lyrics Review UI**: https://gen.nomadkaraoke.com/lyrics/

## Reference Documentation

- `/Users/andrew/Projects/karaoke-gen/README.md` - Main project documentation
- `/Users/andrew/Projects/karaoke-gen/CLAUDE.md` - AI assistant guidelines
- `/Users/andrew/Projects/karaoke-gen/docs/01-reference/` - Reference documentation
- `/Users/andrew/Projects/karaoke-gen/docs/00-current-plan/` - Planning documents (may be outdated)

## Notes

- Some docs in `docs/00-current-plan/` may be outdated - review, evaluate, and move/delete as appropriate
- Focus on making things work, not perfect
- Ship iteratively - fix one thing at a time
- Document issues you find as you go
