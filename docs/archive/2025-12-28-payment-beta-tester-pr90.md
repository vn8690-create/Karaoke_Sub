# PR #90: Payment Flow and Beta Tester Program

**Date**: 2025-12-28
**Branch**: `feature/payment-flow`
**PR**: https://github.com/nomadkaraoke/karaoke-gen/pull/90

## Summary

Implemented customer payment system with Stripe and a beta tester program for low-friction user acquisition.

## What Was Built

### Payment System
- Magic link (passwordless) authentication
- Stripe Checkout integration with credit packages ($5-$30)
- Session management (7-day inactivity, 30-day absolute expiry)
- SendGrid email integration for transactional emails

### Beta Tester Program
- Free credit in exchange for feedback promise
- Users must accept they may need to correct lyrics
- Users must write promise text (min 10 chars)
- Feedback form with ratings (1-5 scale):
  - Overall experience
  - Ease of use
  - Lyrics accuracy
  - Correction experience
- Bonus credit for detailed feedback (50+ chars)
- Admin endpoints for viewing feedback and stats

### Buy Site (buy.nomadkaraoke.com)
- Landing page with credit packages
- Purple gradient beta tester signup section
- Auto-redirect to main app after enrollment

## Key Files Changed

```
backend/
├── models/user.py          # User, Session, MagicLink, Feedback models
├── services/user_service.py      # Auth, credits, beta enrollment
├── services/stripe_service.py    # Stripe checkout & webhooks
├── services/email_service.py     # SendGrid + email templates
└── api/routes/users.py           # All user/auth/beta endpoints

buy-site/
├── app/page.tsx            # Landing page with beta signup
└── lib/api.ts              # API client for beta enrollment

frontend/
└── lib/auth.ts             # Updated for magic link auth
```

## CodeRabbit Fixes Addressed

1. Added try/except for invalid credits metadata in Stripe webhook
2. Fixed magic link race condition with Firestore transaction
3. Moved CSS @import before @tailwind directives
4. Fixed broken Open Graph image URL
5. Removed insecure fallback admin privileges
6. Bumped version to 0.76.26

## Environment Variables Required

```
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
SENDGRID_API_KEY=SG....
EMAIL_FROM=noreply@nomadkaraoke.com
FRONTEND_URL=https://gen.nomadkaraoke.com
BUY_URL=https://buy.nomadkaraoke.com
```

## Next Steps

- [ ] Deploy and test Stripe in live mode
- [ ] Configure SendGrid domain verification
- [ ] Deploy buy-site to GitHub Pages
- [ ] Add feedback request trigger after job completion
- [ ] Monitor beta tester metrics via admin dashboard
