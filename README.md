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

It prints `https://ic4pi--fantm-web.modal.run`.

Vercel (frontend, root directory `frontend`):

- `REACT_APP_BACKEND_URL` = that Modal URL
- Redeploy

Stripe keys are optional. Skip them until you want the Store.

Apply `backend/migrations/001_fantm_schema.sql` on the Supabase `fantm`
project if the tables are not there yet.
