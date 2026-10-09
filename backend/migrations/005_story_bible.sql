-- The author's fixed Story Bible inputs: setting, backstory, themes, point of
-- view, style notes, influences, a locked title, and for memoir/biography the
-- subject and time period. These used to be folded into `prompt`, which only
-- the outline step ever reads — every chapter after that wrote without them.
-- Stored separately so each chapter is written against them and the author
-- can edit them mid-generation. One jsonb object rather than a column per
-- field so the bible can grow without a migration each time.

alter table books add column if not exists bible jsonb not null default '{}'::jsonb;
