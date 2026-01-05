-- Migration: User Preference Sync Tables
-- Table for syncing custom wordlists
create table if not exists user_wordlists (
    user_id uuid primary key,
    words text [],
    updated_at timestamp with time zone default now()
);
-- Table for syncing custom presets
create table if not exists user_presets (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    name text not null,
    settings jsonb not null,
    updated_at timestamp with time zone default now()
);
-- Create index for faster preset lookups by user
create index if not exists idx_user_presets_user_id on user_presets(user_id);
-- Optional: RLS policies could be added here if using Auth,
-- but since we're using a client-side 'user_id' as a key for now
-- (without real auth integration), we'll keep it simple.
-- In a real app, you'd enable RLS and check auth.uid() = user_id.