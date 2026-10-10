# Dial-50 Ambassador Program — Plan

_Status: draft v1 · Owner: TBD · Last updated: 2026-10-10_

## 0. Assumptions to confirm

dial-50.com was not reachable when this was written (the domain does not resolve), so the plan rests on what this repository shows:

- **Product:** a deal-sourcing and outreach platform for investment bankers, business brokers and M&A advisors. It pulls company and financial data (CapIQ, PitchBook, FactSet, Grata, Axial, SEC EDGAR), validates it and runs owner outreach.
- **Business model:** B2B SaaS, sold per seat on a monthly or annual subscription, through self-serve sign-up plus sales-assisted deals.
- **Name:** "Dial-50" suggests a daily-activity discipline (for example, 50 quality touches a day). The program borrows that framing.

If any of these are wrong, mainly the audience or the pricing model, revise sections 2, 4 and 6 first. Everything else carries over.

---

## 1. Goals and success metrics

| Goal | Metric | 6-month target | 12-month target |
|---|---|---|---|
| Lower-cost acquisition | Share of new paid seats from ambassadors | 15% | 25% |
| Pipeline quality | Ambassador-referred trial → paid conversion | ≥ 2× the paid-ads baseline | ≥ 2× the baseline |
| Credibility in the niche | Public content pieces (posts, webinars, case studies) | 40 | 120 |
| Retention | 12-month logo retention of referred accounts | ≥ the company average | +10 pts over the average |
| Program health | Active ambassadors (≥ 1 qualified action per quarter) | 25 | 75 |

**North-star metric:** net new ARR from ambassador-sourced accounts, measured 90 days after close so that churn is netted out.

## 2. Who an ambassador is

Ambassador recruiting starts with people who already use the product and already have reach in the niche.

**Primary profiles**
1. **Power users:** bankers and brokers in the top 10% for usage (outreach volume, data syncs) who have been customers for at least 90 days.
2. **Niche voices:** M&A and search-fund content creators on LinkedIn, X and podcasts, plus newsletter writers (lower middle market, ETA, small business M&A).
3. **Connectors:** M&A attorneys, QoE accountants, SBA lenders and exit-planning advisors who talk to many bankers and brokers but don't compete with them.
4. **Community leaders:** chapter leads and moderators at IBBA, M&A Source, ACG chapters, search-fund communities and MBA/ETA clubs.

**Disqualifiers:** direct competitors or resellers of competing tools, anyone with an open compliance issue, and accounts with high chargeback or abuse risk.

## 3. Program structure: three tiers

| | **Advocate** | **Ambassador** | **Partner** |
|---|---|---|---|
| Who | Any customer in good standing | Accepted by application | By invitation (top performers, connectors) |
| How to join | Self-serve in the app | Application plus a 20-min intro call | Invitation plus a signed partner agreement |
| Commission on referrals | 1 free month per paid referral, for both sides | 20% recurring for 12 months | 25% recurring for 24 months, plus co-selling help |
| Referee offer | 1st month free | 1st month free + 20% off the 1st year (annual plans) | Custom (pilot pricing, onboarding included) |
| Perks | Badge, referral link | Early beta access, private Slack, quarterly swag, featured spotlights | All Ambassador perks + roadmap council seat, co-branded webinars, event sponsorship budget |
| Requirements | None | 1 qualified action per quarter | 3 paid referrals or 2 content pieces per quarter |

**Moving between tiers:** each quarter, the top performers among Advocates are invited to Ambassador and the top Ambassadors to Partner. Ambassadors who do nothing for 2 quarters drop back to Advocate; nobody is removed from the program.

**What counts as a qualified action:** a paid referral, a published post or video about Dial-50, a hosted or co-hosted webinar, a case study or testimonial, a meaningful product feedback session, or a community intro that leads to a demo.

## 4. Rewards and economics

**Commission rules**
- Commission is paid on cash collected, not on bookings. It is held 60 days, which covers the refund window, then paid monthly.
- Attribution: a 90-day cookie, last ambassador click wins, and a unique coupon code overrides the cookie.
- Self-referrals, family accounts and seats inside the ambassador's own firm are excluded.
- Commission caps at $X per referred account per year, to protect margin on enterprise deals. Set the cap once pricing is confirmed.

**Unit-economics check (fill in with real numbers)**
```
Blended CAC today                     = $____
Ambassador CAC = commission + perks + program ops / # referred paid accounts
Target: ambassador CAC ≤ 50% of blended CAC, and LTV:CAC ≥ 4:1
```
Example: a $300/mo seat at 20% recurring for 12 months costs $720 per referred seat. If paid-channel CAC is above $1,500, the program pays for itself quickly.

**Non-cash rewards** (these often matter more to senior bankers than cash)
- Public recognition: a "Dial-50 Ambassador" LinkedIn badge and spotlights in the newsletter and on social.
- Access: roadmap council, beta features, direct line to the founders.
- Deal flow value: an optional, opt-in ambassador directory that sends inbound sell-side leads or partnership requests their way.
- Charity alternative: an ambassador can donate commission to a charity they choose (some firms restrict personal referral fees).

> **Compliance note:** registered reps at FINRA member firms may be barred from taking referral compensation. Every payout should offer a non-cash or charity alternative, and the application should ask whether the ambassador's firm allows referral fees. Have counsel review the terms.

## 5. Ambassador journey

1. **Discover:** in-app banner for top users, an "Earn with Dial-50" page on dial-50.com, personal invitations from CS/sales, and a post-NPS prompt (score ≥ 9 → invite).
2. **Apply:** a short form asking for role, firm, audience size and channels, referral-fee restrictions, and how they use Dial-50.
3. **Onboard (week 1):** welcome email + kit, 20-min kickoff call, private Slack, referral link and code, tracking dashboard.
4. **Activate (first 30 days):** goal is one qualified action. Give them ready-made assets and a "first post" template.
5. **Grow:** monthly ambassador newsletter, quarterly challenges, tier reviews.
6. **Recognize:** quarterly leaderboard, annual "Dial-50 Ambassador of the Year" award, invitation to an in-person dinner at ACG/IBBA events.
7. **Offboard / reactivate:** check-in after a quarter of inactivity, then demotion to Advocate after two. The door stays open.

## 6. Ambassador kit (content and enablement)

- One-pager: what Dial-50 does, who it's for, the 3 headline outcomes (time saved on research, response rates, deals sourced).
- Messaging guide: approved claims, disclosure language ("I'm a Dial-50 ambassador and may earn a commission"), things not to say.
- Swipe file: 5 LinkedIn post templates, 3 email intro templates, 1 short demo script.
- Demo assets: a 2-minute product video, screenshots, a sandbox account with sample company data (the repo's seed data can power it).
- The "Dial-50 challenge": a ready-to-run 30-day challenge ambassadors can invite their audience to (50 quality touches a day, tracked in Dial-50). This is the main viral hook.
- Case-study template plus an interview offer: we write it, they approve it.
- Co-branded webinar playbook: topic ideas such as "Sourcing proprietary deals in the lower middle market," plus a run-of-show and promo assets.

## 7. Product and tech requirements

The program needs a small amount of product work. Buy first, build later.

**Phase 1: buy (weeks 1–4).** Use an off-the-shelf affiliate/referral platform (for example Rewardful, PartnerStack, FirstPromoter or Tolt). It should integrate with the billing provider and handle links, codes, attribution, payouts and tax forms (W-9/W-8BEN, 1099s).

**Phase 2: native features in this repo (after the program shows traction)**
- `backend/app/models/ambassador.py`: `Ambassador` (user_id, tier, status, referral_code, payout_method, compliance_flags) and `Referral` (ambassador_id, referred_user_id, source, status, first_paid_at, commission_amount, paid_out_at).
- `backend/app/api/v1/ambassadors.py`: apply, retrieve profile, list referrals, stats. Admin endpoints for approval, tier changes and payout export.
- Sign-up flow: capture `?ref=` or a code at registration and store it on the user. A Celery task in `backend/app/tasks/` rolls up monthly commissions.
- Frontend: an "Ambassador" page (link/code, copy buttons, referrals table, earnings, assets) and an admin review queue.
- Analytics: add ambassador-sourced pipeline and ARR to `app/services/analytics.py` and the dashboard.
- Audit: log tier changes and payouts through the existing `audit` model.

**Tracking and attribution:** UTM convention `utm_source=ambassador&utm_medium=<channel>&utm_campaign=<code>`. CRM field `lead_source = Ambassador` plus `ambassador_code`, so sales-assisted deals are credited correctly.

## 8. Operations and governance

- **Program owner:** one person (marketing or partnerships, about 0.5 FTE at launch) who owns recruiting, the Slack community, content and payouts.
- **Cadence:** a weekly check of the metrics dashboard, a monthly newsletter and payout run, a quarterly tier review and roadmap council.
- **Terms and policies:** program terms, FTC endorsement disclosure rules, brand usage guidelines, a no-spam policy (no cold bulk email using the Dial-50 name, no paid search bidding on the brand), and the right to claw back fraudulent commissions.
- **Fraud controls:** flag same-IP or same-card sign-ups, block self-referrals, enforce the 60-day hold, and review any referral that churns inside 30 days.
- **Data privacy:** ambassadors see only aggregated or first-name info about referrals, never prospect financial data.

## 9. Budget (first 12 months, rough estimates)

| Item | Estimate |
|---|---|
| Referral platform | $1.2k–$6k/yr |
| Commissions | Variable; budget as ~20–25% of ambassador-sourced first-year revenue |
| Swag and welcome kits (75 × ~$60) | ~$4.5k |
| Events (dinners at ACG/IBBA, 2–3 per year) | $6k–$15k |
| Content support (case-study writing, video) | $5k–$10k |
| Program owner time | 0.5 FTE |

## 10. Launch timeline

| Phase | Weeks | Key work |
|---|---|---|
| **Design** | 1–2 | Confirm the assumptions, finalize tiers and commission rates, legal/compliance review, pick the platform |
| **Build** | 3–5 | Set up the platform and billing integration, write terms, produce the ambassador kit, build the landing page, set up the Slack community |
| **Private beta** | 6–10 | Hand-pick 10–15 founding ambassadors (power users + 2–3 creators), "Founding Ambassador" perks, weekly feedback |
| **Public launch** | 11–12 | Open applications, in-app and email announcement, launch webinar with the founding ambassadors, first Dial-50 Challenge |
| **Scale** | 13–26 | Start tier promotions, partner program for connectors (lenders, attorneys, QoE firms), decide whether to build the native Phase 2 features |
| **Review** | 26 | Six-month review against the section 1 targets: keep, tune or restructure the program |

## 11. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Compliance limits on referral fees at regulated firms | Non-cash and charity options, a compliance question in the application, counsel review |
| Low activation (people join and never act) | 30-day activation goal, ready-made assets, personal kickoff call, a challenge with a deadline |
| Spammy promotion damaging the brand | Messaging guide, no-spam terms, clawbacks, removal for violations |
| Commission cost eating margin on large deals | Per-account cap, custom terms at the Partner tier, payout on cash collected only |
| Low-quality referrals that churn | Pay after the 60-day hold, track 90-day retention by ambassador |
| Attribution disputes | Clear rules (code beats cookie, 90-day window), CRM field for sales-assisted deals |

## 12. Immediate next steps

1. Confirm what Dial-50 is, its pricing and its ICP, then update section 0.
2. Pull the top 50 accounts by usage and NPS as the founding-ambassador candidate list.
3. Get counsel to review referral-fee compliance for FINRA-registered users.
4. Pick a referral platform and confirm it integrates with the billing provider.
5. Draft the founding-ambassador invitation and the "first post" template.
