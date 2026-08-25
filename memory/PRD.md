# fantm.ink — AI Book Generation SaaS

## Original Problem Statement
A SaaS that generates professional-quality novels, memoirs, and biographies from a user prompt using a block-based generation algorithm (running summaries, character tracking, plot-thread continuity) to keep long-form stories coherent. Free/Normal tier + paid Premium tier (illustrations, formatting, editing, PDF export). Rebuilt fresh on FastAPI + MongoDB (old Grok/Supabase/Square integrations were dead).

## User Choices Made
- Text generation: Groq (llama-3.3-70b-versatile), BYOK — user-provided key
- Illustrations: Grok/xAI (deferred, user has not provided key yet)
- Auth: Simple email/password JWT
- Design: Retro-futuristic-spooky (CRT green #39FF14 on black #050505, blood red #8A0303 accents, Space Mono + Cormorant Garamond, 0px radius, scanline/grain overlay)
- Payments: Stripe (claimable sandbox, Flow A) — $9.99/mo Premium plan (lookup_key: premium_monthly)
- Pricing: no old pricing available; set default Free (1 book, short/5 chapters, read-only) vs Premium ($9.99/mo unlimited books, any length, editing, PDF export, illustrations)

## User Personas
- Aspiring authors wanting a full manuscript without writing it themselves
- People chronicling their life story (memoir/biography)
- Hobbyists generating fiction for fun/self-publishing

## Architecture
- **Backend (FastAPI + Motor/MongoDB)**: `server.py` (app + CORS + startup indexes), `db.py` (shared Mongo client), `models.py` (PyObjectId/BaseDocument/User/Book/Chapter), `auth.py` (JWT cookie auth), `books.py` (CRUD + tier gating + PDF export), `generation.py` (Groq block-based generation engine, async background task), `pdf_export.py` (reportlab A5 PDF), `payments.py` (Stripe checkout/status/webhook), `setup_stripe.py` (catalog seed script).
- **Frontend (React + Tailwind + shadcn)**: `AuthContext`, `Navbar`, `ProtectedRoute`, pages: Landing, Login, Register, Dashboard, CreateBook, BookGeneration (live polling via react-query), BookReader (editor + PDF export + illustration placeholder), PaymentSuccess/Cancel, `UpgradeModal`.
- **Generation algorithm**: Groq call 1 generates outline (title/premise/characters/plot_threads/chapter briefs) sized by length (short=5/medium=8/long=12). Then per chapter: Groq call generates prose using running_summary + characters + plot_threads + chapter brief; Groq call 2 updates running_summary/characters/plot_threads for the next chapter. Runs as `asyncio.create_task` background job, polled by frontend every 2.5s.

## What's Been Implemented (2026-07-25)
- Phase 1 (Foundation): Mongo models, JWT auth (register/login/logout/me/refresh, bcrypt, brute-force lockout), user library shell — DONE
- Phase 2 (Generation engine): Block-based Groq generation with running summary/character/plot-thread continuity, live progress polling — DONE, verified end-to-end (coherent 5-chapter novel generated in ~87s)
- Phase 3 (Reader/editor + PDF): Chapter list/reader view, Premium-gated inline chapter editing, A5 PDF export via reportlab — DONE
- Phase 4 (Premium + payments): Stripe Checkout (claimable sandbox, subscription, $9.99/mo), tier gating (free: 1 book/short only/no edit/no PDF; premium: unlimited) — DONE
- AI Illustrations (2026-08-06): Switched from planned xAI/Grok (BYOK) to Pollinations.ai free legacy endpoint (no API key, no cost) per user request to avoid manual signup. Book cover + per-chapter images generated as deterministic URLs during run_generation(). DONE
- Neural Credit Economy (2026-08-06): Replaced binary Free/Premium tiers with a full token-ready credit ledger (designed for future $NEUR migration). 3 literary-themed tiers (Apprentice/Wordsmith/Laureate) with monthly NC stipends that roll over; 6 "Agency Writer" style personas with burn multipliers (1x/1.5x/2x incl. Chimera Blend); illustrations & PDF export now purchased à la carte with NC (2000/5000 NC) instead of tier-gated; Agency Store (5 items) + Refill Packs (3 sizes) purchased with real USD via Stripe. Chapter editing is now free for all tiers. Full ledger/transaction history exposed via /api/credits/transactions and Store page. DONE — 22/22 backend tests, full frontend Apprentice + Laureate journeys verified.
- Phase 5 (Polish + deploy): Not started

## Prioritized Backlog
- P1: credits.adjust_balance is not atomic (separate $inc + ledger insert) — fine for MVP, would need a Mongo transaction/idempotency key before real-money-adjacent ledger integrity at scale
- P1: books.create_book estimates cost upfront but actual burn happens per-chapter after generation — a user right at the balance boundary could slightly overspend if real word count exceeds the estimate; consider reserving the estimate or capping generation
- P1: Stripe webhook production hardening; rate limiting on generation endpoint; subscription cancel/downgrade flow
- P2: Legacy pre-economy books (e.g. "The Clockwork Requiem") default to illustrations_unlocked=false — confirm migration policy for old books when convenient
- P2: Richer PDF styling (chapter drop-caps, table of contents), EPUB export, collaborative/sharing features, subscription management page (cancel/view billing)

## Next Tasks
- Confirm migration policy for legacy books' illustrations_unlocked flag
- Deploy readiness pass (Phase 5) when user is ready to go live
