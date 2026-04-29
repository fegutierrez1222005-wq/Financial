# Zibs — Pre-launch Site

Next.js 14 + Tailwind CSS pre-launch landing page for **Zibs**, a zero-nicotine
mucoadhesive buccal pouch for gum health.

> Patent Pending · USPTO Provisional · Filed April 2026.

## Stack

- Next.js 14 (App Router)
- React 18
- Tailwind CSS 3
- TypeScript 5
- Resend for waitlist email delivery

Typography uses Cormorant Garamond (display) and DM Sans (body), both loaded
from Google Fonts via `next/font`.

## Quick start

```bash
npm install
npm run dev
```

The site runs at <http://localhost:3000>.

## Environment variables

Copy `.env.example` to `.env.local` and fill in:

```
RESEND_API_KEY=
WAITLIST_FROM_EMAIL="Zibs Waitlist <waitlist@zibs.com>"
WAITLIST_NOTIFY_EMAIL=founders@zibs.com
```

When `RESEND_API_KEY` is absent the waitlist API still returns a success
response (logged locally) so the front-end works in dev. In production set the
key in Vercel and emails will be delivered through Resend.

## Deploying to Vercel

1. Push this repo to a Git remote.
2. Import the repo into Vercel — the project root contains `package.json`, no
   subfolder configuration needed.
3. Add the environment variables above under **Project Settings → Environment
   Variables**.
4. Deploy. No further configuration required.

## Page sections

- `Nav` — minimal nav with `Join Waitlist` CTA
- `Hero` — “Keep the pouch. Lose the damage.” headline + tin render
- `Stats` — 47% gum disease, 20 minutes daily, 30 count
- `HowItWorks` — Place it / Let it work / Protect your gums
- `Ingredients` — Collagen amino acids, CoQ10, Vitamin C, HPMC
- `Waitlist` — email capture wired to `/api/waitlist`
- `Footer` — Patent pending · 2026 · Zero nicotine · Dietary supplement
