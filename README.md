# Zibs — Pre-launch Site

Next.js 14 + Tailwind CSS pre-launch landing page for **Zibs**, a zero-nicotine
mucoadhesive buccal pouch for gum health.

> Patent Pending · USPTO Provisional · Filed April 2026.

---

## Run locally (the only three commands you need)

> **Open a terminal in the project folder first.** That's the folder that
> contains this `README.md` and a `package.json`. If `ls` doesn't show
> `package.json`, you're in the wrong folder — `cd` into the right one.

```bash
node -v       # must print v18.18 or higher (v20+ recommended)
npm install
npm run dev
```

Then open **<http://localhost:3000>** in your browser. Use `http://`, not
`https://`. The first request takes ~2 seconds to compile.

To stop the server: press `Ctrl+C` in the terminal.

---

## If `npm run dev` doesn't work, walk through this list

Fix these in order — one of them is almost always the cause.

**1. You ran the command from the wrong folder.**
Run `pwd` and `ls`. The output of `ls` must include `package.json`,
`next.config.mjs`, and an `app/` folder. If it doesn't, you're inside the
wrong folder. `cd` into the project root and try again.

**2. You skipped `npm install`.**
`node_modules/` and a `.next/` folder must exist. If `node_modules/` isn't
there, you'll see errors like `next: command not found` or
`Cannot find module 'next'`. Run `npm install` and re-run `npm run dev`.

**3. Your Node version is too old.**
Run `node -v`. Anything below `v18.18.0` will fail to start Next.js 14. Install
Node 20 LTS from <https://nodejs.org/> (or use `nvm install 20 && nvm use 20`).

**4. Port 3000 is already in use.**
You'll see `EADDRINUSE` or `Port 3000 is in use`. Either kill the other
process or run on a different port:
```bash
PORT=3001 npm run dev
```
Then visit <http://localhost:3001>.

**5. You typed `https://localhost:3000` instead of `http://`.**
The dev server only speaks HTTP. Browsers will refuse `https://` with
`ERR_SSL_PROTOCOL_ERROR` or `This site can't provide a secure connection`.
Use `http://localhost:3000`.

**6. Browser shows "This site can't be reached" / `ERR_CONNECTION_REFUSED`.**
Confirm the dev server is actually running. The terminal must show:
```
▲ Next.js 14.2.33
- Local: http://localhost:3000
✓ Ready in ...
```
If you don't see those lines, the server crashed — scroll up in the terminal
to find the red error message. Copy the first error line; that tells you
what's actually wrong.

**7. You're on a corporate VPN, WSL, or a remote machine.**
- **WSL:** Use `npm run dev:lan` (binds to `0.0.0.0`) and visit the WSL IP from
  Windows, or just `http://localhost:3000` — newer WSL2 forwards it.
- **Remote VM / SSH:** Forward the port — `ssh -L 3000:localhost:3000 ...`
  then open `http://localhost:3000` on your laptop.
- **VPN / corporate firewall:** Try a different port (`PORT=3001 npm run dev`)
  or temporarily disable the VPN.

**8. Page loads but every section looks unstyled (white background, plain
fonts).**
Tailwind didn't compile. Stop the server (`Ctrl+C`), delete the cache, and
restart:
```bash
rm -rf .next
npm run dev
```

**9. Waitlist form returns an error.**
With no `RESEND_API_KEY`, the API still returns success in dev. If you set the
key in `.env.local` and the request 500s, the most common cause is an
unverified `WAITLIST_FROM_EMAIL` domain in Resend. Either remove
`WAITLIST_FROM_EMAIL` from `.env.local` (defaults to `Zibs <waitlist@zibs.com>`)
or use a Resend-verified sender.

---

## Stack

- Next.js 14.2.33 (App Router)
- React 18
- Tailwind CSS 3
- TypeScript 5
- Resend for waitlist email delivery

Typography uses Cormorant Garamond (display) and DM Sans (body), both loaded
from Google Fonts via `next/font`.

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
2. Import the repo into Vercel — `package.json` is at the project root, no
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

## Scripts

| Script | What it does |
|---|---|
| `npm run dev` | Dev server on `localhost:3000` |
| `npm run dev:lan` | Dev server bound to `0.0.0.0:3000` (LAN / WSL) |
| `npm run build` | Production build |
| `npm run start` | Run the production build |
| `npm run lint` | Lint with `next lint` |
