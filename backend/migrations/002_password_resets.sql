-- Adds password reset tokens, used by /api/auth/forgot-password and
-- /api/auth/reset-password. Tokens are stored hashed (sha256) so a DB leak
-- doesn't hand out usable reset links.

create table if not exists password_resets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users(id) on delete cascade,
  token_hash text not null,
  expires_at timestamptz not null,
  used boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists idx_password_resets_user_id on password_resets(user_id);
