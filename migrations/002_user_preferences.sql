-- Migration: 002_user_preferences
-- Description: Create tables for syncing user wordlists and presets
-- 1. User Wordlists Table
create table if not exists user_wordlists (
    user_id uuid,
    -- unique identifier provided by the app (config.sync.user_id)
    words text [] default '{}',
    updated_at timestamp with time zone default now(),
    primary key (user_id)
);
comment on table user_wordlists is 'Stores custom profanity wordlists for users synced across devices.';
-- 2. User Presets Table
create table if not exists user_presets (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    name text not null,
    settings jsonb not null default '{}'::jsonb,
    updated_at timestamp with time zone default now(),
    -- ensure unique preset name per user
    unique(user_id, name)
);
comment on table user_presets is 'Stores custom filter presets for users synced across devices.';
-- 3. RLS Policies (Optional: Enable if Auth is active, but currently using shared ANON key)
-- For now, we assume the app manages uniqueness via the provided UUID.
-- If we were using Supabase Auth, we would check referencing auth.uid()
alter table user_wordlists enable row level security;
alter table user_presets enable row level security;
-- Allow anonymous access for this app's architecture (client uses user_id)
-- Note: In production with Auth, change this to check auth.uid()
create policy "Allow public access for app sync" on user_wordlists for all using (true) with check (true);
create policy "Allow public access for app sync" on user_presets for all using (true) with check (true);