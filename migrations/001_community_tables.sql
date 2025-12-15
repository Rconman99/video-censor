-- ============================================================================
-- Video Censor Community Timestamps - Supabase Schema
-- Run this in your Supabase SQL Editor: https://supabase.com/dashboard
-- ============================================================================

-- 1. Contributors table (anonymous users with trust scores)
CREATE TABLE IF NOT EXISTS contributors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  device_id TEXT UNIQUE NOT NULL,
  trust_score FLOAT DEFAULT 1.0,
  contribution_count INT DEFAULT 0,
  helpful_votes INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Voting table (track up/downvotes per detection)
CREATE TABLE IF NOT EXISTS video_votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  detection_id UUID REFERENCES video_detections(id) ON DELETE CASCADE,
  device_id TEXT NOT NULL,
  vote INT CHECK (vote IN (-1, 1)),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(detection_id, device_id)
);

-- 3. Extend video_detections table with community fields
-- (Run these one at a time if table already exists)
ALTER TABLE video_detections 
  ADD COLUMN IF NOT EXISTS contributor_id UUID REFERENCES contributors(id),
  ADD COLUMN IF NOT EXISTS upvotes INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS downvotes INT DEFAULT 0;

-- 4. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_contributors_device_id ON contributors(device_id);
CREATE INDEX IF NOT EXISTS idx_video_votes_detection_id ON video_votes(detection_id);
CREATE INDEX IF NOT EXISTS idx_video_detections_file_hash ON video_detections(file_hash);
CREATE INDEX IF NOT EXISTS idx_video_detections_contributor_id ON video_detections(contributor_id);

-- 5. Row Level Security (RLS) - Enable for security
ALTER TABLE contributors ENABLE ROW LEVEL SECURITY;
ALTER TABLE video_votes ENABLE ROW LEVEL SECURITY;

-- Allow anonymous reads and inserts (required for the app)
CREATE POLICY "Allow anonymous read contributors" ON contributors
  FOR SELECT USING (true);

CREATE POLICY "Allow anonymous insert contributors" ON contributors
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow anonymous update own contributors" ON contributors
  FOR UPDATE USING (true);

CREATE POLICY "Allow anonymous read votes" ON video_votes
  FOR SELECT USING (true);

CREATE POLICY "Allow anonymous insert votes" ON video_votes
  FOR INSERT WITH CHECK (true);

CREATE POLICY "Allow anonymous upsert votes" ON video_votes
  FOR UPDATE USING (true);

-- Allow anonymous access to video_detections (already should exist)
CREATE POLICY IF NOT EXISTS "Allow anonymous read detections" ON video_detections
  FOR SELECT USING (true);

CREATE POLICY IF NOT EXISTS "Allow anonymous insert detections" ON video_detections
  FOR INSERT WITH CHECK (true);

CREATE POLICY IF NOT EXISTS "Allow anonymous update detections" ON video_detections
  FOR UPDATE USING (true);
