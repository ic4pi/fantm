# fantm.ink — AI long-form manuscript generator

React parlour UI + FastAPI. Outline, then chapter-by-chapter prose with a
running summary so page 40 still knows page 2.

## Generate a book (once it's deployed)

1. Open [fantm.ink](https://fantm.ink) (or the Vercel URL)
2. Register
3. **New book** → short novel → House style → Generate

A new Apprentice account has 5000 NC, enough for one short book.

## Deploy

The API cannot live on Vercel — generation is a background task in the web
process. It runs on Modal. The UI stays on Vercel.

On the machine where `modal` already works (`c4p1`):

```bash
cd ~
git clone https://github.com/ic4pi/fantm.git
cd fantm

modal secret create fantm-env \
  DATABASE_URL='postgresql://…supabase…' \
  JWT_SECRET='paste 32+ random chars' \
  GROQ_API_KEY='gsk_…' \
  CORS_ORIGINS='https://fantm.ink,https://YOUR-FRONTEND.vercel.app'

modal deploy backend/modal_app.py
```

It prints `https://jeremy-f-wall--fantm-web.modal.run`.

Vercel (frontend, root directory `frontend`) reaches the API through the
`/api` rewrite in `frontend/vercel.json`, so auth cookies stay first-party.
Point that rewrite at the Modal URL and leave `REACT_APP_BACKEND_URL` empty.

Stripe keys are optional. Skip them until you want the Store.

The API applies `backend/migrations/*.sql` itself on startup, so a new
database needs no manual setup. A daily GitHub Action
(`.github/workflows/keep-awake.yml`) pings `/api/health` so the free-tier
Supabase database never pauses.
