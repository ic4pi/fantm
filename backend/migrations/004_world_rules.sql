-- Special/non-normal-world rules and satire hooks (e.g. "gravity reverses on
-- Tuesdays", a running list of absurd things the story can draw on). Same
-- shape and treatment as plot_threads: a list of short strings, present in
-- every chapter's generation context, not just the initial outline.

alter table books add column if not exists world_rules jsonb not null default '[]'::jsonb;
