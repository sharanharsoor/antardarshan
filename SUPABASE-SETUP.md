# Supabase Setup — AntarDarshan

Complete first-time setup guide. Takes about 20 minutes.

---

## Step 1: Create Supabase Project

1. Go to [https://supabase.com](https://supabase.com) and sign up (free)
2. Click **"New project"**
3. Fill in:
  - **Name:** `antardarshan`
  - **Database password:** choose a strong password — save it somewhere
  - **Region:** pick closest to India (e.g. `ap-south-1` Mumbai or `ap-southeast-1` Singapore)
4. Click **"Create new project"** — takes ~2 minutes to provision

---

## Step 2: Get Your API Keys

Once the project is ready, go to:  
**Project Settings → API**

Copy these three values:


| Variable               | Where to find it          | Example                               |
| ---------------------- | ------------------------- | ------------------------------------- |
| `SUPABASE_URL`         | "Project URL"             | `https://abcdefgh.supabase.co`        |
| `SUPABASE_ANON_KEY`    | "anon public" key         | `eyJhbGci...` (long string)           |
| `SUPABASE_SERVICE_KEY` | "service_role secret" key | `eyJhbGci...` (different long string) |


---

## Step 3: Create the Database Schema

Go to **SQL Editor** in your Supabase dashboard and run this SQL:

```sql
-- ══════════════════════════════════════════════════════════
-- AntarDarshan Database Schema
-- Run this entire block in Supabase SQL Editor
-- ══════════════════════════════════════════════════════════

-- Reading progress: where user left off in each scripture
CREATE TABLE IF NOT EXISTS reading_progress (
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,           -- scripture slug (URL-safe)
    chapter     INTEGER NOT NULL DEFAULT 1,
    verse       INTEGER NOT NULL DEFAULT 1,
    updated_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, slug)
);

-- Bookmarks: specific verse bookmarks with optional note
CREATE TABLE IF NOT EXISTS bookmarks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    scripture   TEXT NOT NULL,
    chapter     INTEGER NOT NULL,
    verse       INTEGER NOT NULL,
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Highlights: selected text within a verse with color + note
CREATE TABLE IF NOT EXISTS highlights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug            TEXT NOT NULL,
    scripture       TEXT NOT NULL,
    chapter         INTEGER NOT NULL,
    verse           INTEGER NOT NULL,
    selected_text   TEXT NOT NULL,
    color           TEXT DEFAULT 'yellow',   -- yellow | green | blue | pink
    note            TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations: Q&A chat sessions
CREATE TABLE IF NOT EXISTS conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    title       TEXT,                    -- auto-set from first user message
    shared      BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Messages: individual messages within a conversation
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT NOT NULL,
    citations       JSONB,               -- [{scripture, chapter, verse, translator}]
    mode            TEXT,                -- citation | well_being | comparison | exploration
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback on AI responses
CREATE TABLE IF NOT EXISTS feedback_responses (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    message_id      UUID REFERENCES messages(id) ON DELETE CASCADE,
    rating          SMALLINT NOT NULL CHECK (rating IN (-1, 1)),  -- -1 = thumbs down, 1 = up
    comment         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback on books/scriptures in the library
CREATE TABLE IF NOT EXISTS feedback_books (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    scripture   TEXT NOT NULL,
    rating      SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    comment     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, slug)              -- one rating per user per book
);

-- Issue reports on specific verses (OCR errors, wrong content, etc.)
CREATE TABLE IF NOT EXISTS issue_reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    scripture   TEXT NOT NULL,
    chapter     INTEGER,
    verse       INTEGER,
    issue_type  TEXT NOT NULL,           -- 'ocr_garbage' | 'wrong_content' | 'missing_text' | 'other'
    comment     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Leaderboard opt-in and display preferences
CREATE TABLE IF NOT EXISTS leaderboard_settings (
    user_id         UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    opted_in        BOOLEAN DEFAULT FALSE,
    display_name    TEXT,                -- shown on leaderboard instead of email
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ══════════════════════════════════════════════════════════
-- Row Level Security (RLS) — users can only see their own data
-- ══════════════════════════════════════════════════════════

ALTER TABLE reading_progress   ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookmarks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE highlights         ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations      ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages           ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_responses ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_books     ENABLE ROW LEVEL SECURITY;
ALTER TABLE issue_reports      ENABLE ROW LEVEL SECURITY;
ALTER TABLE leaderboard_settings ENABLE ROW LEVEL SECURITY;

-- reading_progress policies
CREATE POLICY "Users read own progress"   ON reading_progress FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users write own progress"  ON reading_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own progress" ON reading_progress FOR UPDATE USING (auth.uid() = user_id);

-- bookmarks policies
CREATE POLICY "Users read own bookmarks"   ON bookmarks FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users write own bookmarks"  ON bookmarks FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own bookmarks" ON bookmarks FOR DELETE USING (auth.uid() = user_id);

-- highlights policies
CREATE POLICY "Users read own highlights"   ON highlights FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users write own highlights"  ON highlights FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own highlights" ON highlights FOR DELETE USING (auth.uid() = user_id);

-- conversations: own + shared
CREATE POLICY "Users read own conversations"   ON conversations FOR SELECT
    USING (auth.uid() = user_id OR shared = TRUE);
CREATE POLICY "Users write own conversations"  ON conversations FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own conversations" ON conversations FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Users delete own conversations" ON conversations FOR DELETE USING (auth.uid() = user_id);

-- messages: accessible if user owns the conversation
CREATE POLICY "Users read conversation messages" ON messages FOR SELECT
    USING (EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.id = messages.conversation_id
        AND (c.user_id = auth.uid() OR c.shared = TRUE)
    ));
CREATE POLICY "Users write messages" ON messages FOR INSERT
    WITH CHECK (EXISTS (
        SELECT 1 FROM conversations c
        WHERE c.id = messages.conversation_id AND c.user_id = auth.uid()
    ));

-- Note: no DELETE on individual messages by design — conversations are atomic.
-- To delete messages, delete the parent conversation (cascades automatically).

-- feedback
CREATE POLICY "Users manage own response feedback" ON feedback_responses
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own book feedback" ON feedback_books
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own issue reports" ON issue_reports
    FOR ALL USING (auth.uid() = user_id);
CREATE POLICY "Users manage own leaderboard settings" ON leaderboard_settings
    FOR ALL USING (auth.uid() = user_id);

-- ══════════════════════════════════════════════════════════
-- Indexes for fast lookups
-- ══════════════════════════════════════════════════════════

CREATE INDEX IF NOT EXISTS idx_bookmarks_user     ON bookmarks(user_id, slug);
CREATE INDEX IF NOT EXISTS idx_highlights_user    ON highlights(user_id, slug, chapter, verse);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conv      ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_resp_user ON feedback_responses(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_books_slug ON feedback_books(slug);
```

---

## Step 4: Enable Google Login (Optional but Recommended)

1. In Supabase dashboard: **Authentication → Providers → Google**
2. Toggle **Enable**
3. You need a Google OAuth client ID:
  - Go to [https://console.cloud.google.com](https://console.cloud.google.com)
  - Create a new project (or use existing)
  - Enable "Google+ API"
  - Go to **Credentials → Create OAuth 2.0 Client ID**
  - Application type: **Web application**
  - Authorized redirect URIs: `https://your-project-id.supabase.co/auth/v1/callback`
  - Copy the Client ID and Client Secret into Supabase
4. Also add to **Authorized JavaScript origins**: `http://localhost:3000`

**For now you can skip Google and just use Email Magic Link** — Supabase has this built in, no extra setup needed.

---

## Step 5: Add Keys to Your .env Files

**Backend** (`/Users/sharsoor/Desktop/exp/person/bhagwatgita/.env`):

```bash
# Add these lines:
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key   # used server-side only
```

**Frontend** (`/Users/sharsoor/Desktop/exp/person/bhagwatgita/frontend/.env.local`):

```bash
# Add these lines:
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-public-key
```

---

## Step 6: Install Supabase Client Libraries

```bash
# Frontend
cd frontend
npm install @supabase/supabase-js @supabase/ssr

# Backend (Python)
cd ..
source .venv/bin/activate
pip install supabase
```

---

## What to Tell Me When Done

Once you've:

1. ✅ Created the Supabase project
2. ✅ Run the SQL schema
3. ✅ Added the env vars to both `.env` files
4. ✅ Run `npm install @supabase/supabase-js @supabase/ssr` in the frontend

Say "Supabase is ready" and I'll wire in:

- Login/logout UI in the header
- Auth middleware protecting user-data routes
- Reading progress auto-save
- Bookmarks working end-to-end

---

## Embedding Status (check while you set up Supabase)

```bash
tail -5 /tmp/embed.log
```

When you see `✅ All good.` — restart the backend with `./start.sh`.