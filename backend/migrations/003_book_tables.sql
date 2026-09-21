-- Freeform per-book reference tables — a sports schedule, a timeline of
-- events, a map of locations, anything the author wants tracked and fed
-- back into generation. Deliberately schemaless (columns/rows as jsonb)
-- rather than a fixed "timeline" or "characters" shape, so the author adds
-- whatever table a given story actually needs instead of being limited to
-- ones we anticipated.

create table if not exists book_tables (
  id uuid primary key default gen_random_uuid(),
  book_id uuid not null references books(id) on delete cascade,
  name text not null,
  columns jsonb not null default '[]'::jsonb,
  rows jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_book_tables_book_id on book_tables(book_id);
