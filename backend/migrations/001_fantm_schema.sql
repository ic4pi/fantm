-- fantm.ink — Postgres schema (replaces MongoDB)
-- Mirrors the current Mongo document shapes 1:1 so the app's behavior is
-- unchanged; only the storage layer moves. Left the existing
-- profiles/stories/payments/autosaves/genres tables untouched — those are
-- the pre-credit-economy build and nothing here depends on them.

create extension if not exists pgcrypto;

create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text not null,
  name text not null,
  tier text not null default 'apprentice',
  credit_balance integer not null default 0,
  last_stipend_at timestamptz,
  stripe_subscription_id text,
  created_at timestamptz not null default now()
);

create table if not exists books (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  title text not null default 'Generating...',
  book_type text not null,
  genre text not null default '',
  tone text not null default '',
  length text not null,
  style text not null default 'house',
  style_secondary_a text,
  style_secondary_b text,
  prompt text not null,
  premise text not null default '',
  characters jsonb not null default '[]'::jsonb,
  plot_threads jsonb not null default '[]'::jsonb,
  running_summary text not null default '',
  outline jsonb not null default '[]'::jsonb,
  total_chapters integer not null default 0,
  current_chapter integer not null default 0,
  status text not null default 'pending',
  error text,
  cover_image_url text,
  illustrations_unlocked boolean not null default false,
  pdf_unlocked boolean not null default false,
  reserved_nc integer not null default 0,
  settled boolean not null default false,
  burned_nc integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_books_user_id on books(user_id);

create table if not exists chapters (
  id uuid primary key default gen_random_uuid(),
  book_id uuid not null references books(id) on delete cascade,
  index integer not null,
  title text not null,
  content text not null default '',
  word_count integer not null default 0,
  status text not null default 'pending',
  image_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_chapters_book_id on chapters(book_id);

create table if not exists credit_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  type text not null,
  amount integer not null,
  balance_after integer not null,
  description text not null default '',
  related_book_id uuid references books(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists idx_credit_tx_user_created on credit_transactions(user_id, created_at desc);

create table if not exists payment_transactions (
  id uuid primary key default gen_random_uuid(),
  session_id text unique not null,
  user_id uuid not null references users(id) on delete cascade,
  purpose text not null,
  key text not null,
  lookup_key text not null,
  amount numeric not null default 0,
  currency text not null default 'usd',
  status text not null default 'initiated',
  payment_status text not null default 'pending',
  stripe_subscription_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_payment_tx_user_id on payment_transactions(user_id);

create table if not exists login_attempts (
  identifier text primary key,
  count integer not null default 0,
  locked_until timestamptz
);
