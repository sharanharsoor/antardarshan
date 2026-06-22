# AntarDarshan — V1 Feature Roadmap

> **Source:** User vision session, Jun 20 2026. Organized by Claude Sonnet 4.6.  
> **Last reviewed:** Claude Opus 4 + Codex 5.3 (Jun 20 2026) — 164/164 tests passing, 21/25 eval (84%).  
> **Purpose:** Living todo list. Every feature below has a priority, feasibility note, and cost impact.  
> **Rule:** Nothing ships to prod without being checked off here first.

### Already Shipped Baseline (locked)

- Supabase auth (Google + magic link) is live.
- Bookmarks and reading progress are live and tested.
- Favicon is in place.
- Incremental indexing CLI exists.
- Hybrid retrieval pipeline is live (bge-m3 dense+sparse, reranker, source balancing).

Roadmap below tracks what remains, plus refinements to avoid rework.

---

## Cost Verdict: Still $6/month ✅

Adding auth, user profiles, bookmarks, highlights, chat history, and leaderboard does NOT change the cost:

| Addition | Service | Cost |
|---|---|---|
| Auth + user DB | Supabase free (50K MAU, 500MB DB) | $0 |
| User-uploaded books (storage) | Cloudflare R2 (10GB free) | $0 |
| Everything else | Same Hetzner VPS | $0 extra |
| **Total** | | **~$6/month** |

Breaks $6/month only at sustained 1,500+ DAU (Groq limits). Good problem to have.

---

## Feature Tiers

> Numbering is tier-local (used for navigation), not a global sequence.

### TIER 1 — V1 Must-Have (remaining before public launch)

#### 1. Incremental Indexing Pipeline
**Status:** ✅ Already implemented (keep as maintenance item).  
**What:** Add or remove a single scripture without re-embedding the entire 19K-chunk corpus.  
**Why:** Currently any fix requires full re-index (hours). With incremental: new file → parse → embed → upsert into Qdrant in minutes.  
**How:**
- `corpus/index_state.json` — tracks which files are indexed, their hash, chunk count
- CLI: `python -m ingestion.admin add corpus/raw/new_file.txt`
- CLI: `python -m ingestion.admin remove "Scripture Name"`
- Qdrant supports per-point upsert and delete-by-filter — no full re-index needed
- Admin web page (password-protected, `/admin`) with file picker → index button

**Feasibility:** Straightforward. 1-2 days.  
**Cost impact:** None.

---

#### 2. Favicon + Browser Icon
**Status:** ✅ Already implemented.  
**What:** Replace the ⚠️ browser tab icon with a proper AntarDarshan icon.  
**How:** Generate SVG favicon (book + lamp motif, saffron color). Add to `public/` folder in Next.js. Add `apple-touch-icon`.  
**Feasibility:** 30 minutes.  
**Cost impact:** None.

---

#### 3. Query Quota Display
**What:** Show query availability in the Q&A top bar.  
**Two levels:**
- **Global** (always shown): Green/yellow/red dot based on % of daily org-level Groq limit used (tracked internally in SQLite — Groq does not expose remaining quota via API).
- **Per-user** (logged-in only): Track each user's queries in Supabase. Show `● 47 of 50 queries left today`. Resets at midnight UTC.
**API contract lock:** Keep `GET /api/quota-status` as canonical (already implemented). Add `GET /api/quota` only as optional alias if needed.
**Note (from Codex 5.3 review):** Global and per-user are independent systems. Global protects the org budget. Per-user prevents one user from burning everyone's quota.  
**Feasibility:** Medium (needs auth for per-user, easy for anonymous by IP).  
**Cost impact:** None.

---

#### 4. Shareable Conversation URLs
**What:** Every Q&A session gets a permanent UUID-based URL (`/ask/c/{uuid}`). User can share it; recipients see it read-only.  
**How:**
- On session create: generate UUID, store in Supabase `conversations` table with `shared=false`
- "Share" button copies URL, sets `shared=true`
- Shared view: read-only, no input box, shows full conversation
- Like ChatGPT/Cursor: new chat = new URL, URL stable across page refreshes

**Note (from Codex 5.3 review):** This requires conversations to be stored permanently in Supabase (not just sessionStorage). The current sessionStorage approach is a stepping stone — this feature is the migration to persistent storage. Budget 2-3 days, not 1.  
**Feasibility:** Medium-hard (requires Supabase conversations table + migration from sessionStorage).  
**Cost impact:** None.

---

#### 5. Q&A Feedback (Thumbs Up/Down + Comment)
**What:** After each AI response, user can rate it and optionally leave a comment.  
**Currently:** UI buttons exist, backend not wired.  
**How:** POST `/api/feedback` → store in `feedback_responses` table → use to improve retrieval weights over time.  
**Feasibility:** Easy. Backend endpoint + 1 DB table. Half a day.

---

#### 6. Book-Level Feedback (Library)
**What:** On each book card in the library, user can thumbs up/down + comment.  
**Why:** If many users report a source as garbage OCR, we know to remove it from library or fix it. High thumbs-up = boost that scripture's weight in RAG.  
**Feasibility:** Easy. Same pattern as Q&A feedback.

---

#### 7. Text Issue Reporting
**What:** In reading mode, a "Report an issue" button (flag icon). User selects: OCR garbage / wrong content / other. Optional comment.  
**Response:** Automated reply: "This text comes from a 19th-century OCR scan. We know about this issue." or mark for human review.  
**Feasibility:** Easy. 1 DB table + email/Slack notification to you.

---

#### 8. Contextual Re-indexing (Anthropic Technique) ⬆️ PROMOTED TO TIER 1
**What:** Before embedding each chunk, prepend 50-100 tokens of context ("This verse is from Chapter 2 of the Bhagavad Gita, where Krishna explains Buddhi Yoga to Arjuna...").  
**Why:** Improves retrieval accuracy by 49-67% (Anthropic benchmarks). The embedding captures WHERE the verse sits philosophically, not just WHAT it says. Directly addresses remaining eval misses (grief/karma-yoga/meditation/death routing).  
**How:** One-time batch job. For each chunk → call Groq Llama 8B to generate context prefix → re-embed → re-upload to Qdrant.  
**Cost:** 19K+ chunks × ~300 tokens = ~6M tokens through Groq 8B free tier = a few days of batch processing. $0.  
**Feasibility:** Medium. 1 day to build + 1-2 days to run and validate.

---

### TIER 2 — Core Reading Experience (Kindle-like, needs auth)

#### 8. Auth (Supabase)
**Status:** ✅ Already implemented (Google + magic link).  
**What:** Sign in with Google / email OTP. Anonymous users keep current experience. Signed-in users get bookmarks, highlights, progress tracking, history.  
**Why this comes first in Tier 2:** Everything below (9-15) depends on knowing WHO the user is.  
**Feasibility:** Medium. Supabase + Next.js integration is well-documented. 1-2 days.  
**Cost:** $0 (Supabase free: 50K MAU).

---

#### 9. Reading Progress + Resume
**Status:** ✅ Baseline implemented; resume UX polish pending.  
**What:** Track which chapter/verse the user last read. When they return to a book, offer "Resume from Chapter 3, Verse 7."  
**DB schema:** `reading_progress(user_id, slug, chapter, verse, updated_at)`  
**Frontend:** "Continue Reading" card on library page, auto-scroll to last position.  
**Feasibility:** Medium. 1 day.

---

#### 10. Bookmarks
**Status:** ✅ Baseline implemented; profile/list UX pending.  
**What:** Bookmark any verse at exact position. View all bookmarks in user profile.  
**Currently:** Core save/remove is wired; profile organization/search UX is pending.  
**DB schema:** `bookmarks(user_id, slug, scripture, chapter, verse, note, created_at)`  
**Feasibility:** Easy once auth exists. Half a day.

---

#### 11. Highlights + Notes
**What:** Select any text in reading mode → highlight it (color options) → optionally add a private note.  
**How:** Store character offset or verse reference + selected text. Render highlighted text on re-visit.  
**DB schema:** `highlights(user_id, slug, scripture, chapter, verse, selected_text, color, note)`  
**Feasibility:** Medium-hard (text selection UX is tricky). 2-3 days.

---

#### 12. Select Text → Ask AI
**What:** User selects a passage → "Ask about this" button appears → opens Q&A with that passage pre-filled as context.  
**How:** `window.getSelection()` on text selection → button appears → routes to `/ask?context={encoded_text}`.  
**Feasibility:** Medium. 1 day.

---

#### 13. User Profile Page
**What:** `/profile` page showing:
- Books currently reading (with %)
- Books completed
- Highlights saved
- Q&A history (past conversations)
- Feedback given
**Feasibility:** Medium. 1-2 days once auth + other features exist.

---

#### 14. Q&A History (Chat Sidebar)
**What:** Left sidebar (like ChatGPT/Cursor) listing past conversations with auto-generated titles.  
**How:** Store conversations in Supabase. Title = first user message truncated. Clicking loads that conversation.  
**Feasibility:** Medium. 2 days.

---

#### 15. LLM Context + Model Display
**What:** Small indicator in Q&A showing which model was used and approximately how much context was consumed.  
**Example:** `Model: Llama 3.1 8B · ~2,400 tokens used`  
**How:** Backend already knows this. Just pass it in the response payload.  
**Feasibility:** Easy. Half a day.

---

### TIER 3 — Post-V1 (after real users validate Tier 1+2)

#### 16. User-Uploaded Books (PDF / EPUB / TXT)
**What:** User uploads their own spiritual book. We parse + chunk it. They can read it with all the same features (highlight, ask, bookmark). We recommend it stay spiritual.  
**How:**
- File upload → Cloudflare R2 (storage)
- Backend: parse PDF (PyMuPDF) → chunk → embed → store in user-scoped Qdrant collection
- Private books: never shown in public library, never used in RAG for other users
- Supported formats: PDF, TXT, EPUB (with ebooklib)
**Cost:** Cloudflare R2 free tier = 10GB. ~5MB per book → 2,000 books free.  
**Feasibility:** Medium-hard. 3-4 days. Needs careful privacy isolation.  
**Privacy rule:** Private books never appear in leaderboard, never leak to other users.

---

#### 17. Leaderboard (Privacy-First)
**What:** Show reading activity across the community. Completely opt-in.  
**Shows:** Hours read this week, books finished, questions asked — aggregated.  
**Never shows:** Which book someone reads (private books especially), email, real name.  
**Display name:** User-chosen handle or anonymous.  
**Feasibility:** Easy once user stats exist. 1 day.

---

#### 18. Citation Verification Layer
**What:** Before returning an LLM response, verify every cited verse actually exists in our corpus. If not → strip that citation.  
**Currently:** Prompt tells LLM to only cite retrieved sources. Hallucination still possible.  
**How:** Parse LLM output for citation patterns → check against corpus index → remove invalid ones.  
**Feasibility:** Medium. 1 day.

---

#### 20. HyDE (for Emotional/Abstract Queries)
**What:** "I feel lost and don't know my purpose" → instead of embedding the raw query, generate a hypothetical philosophical answer first → embed THAT → retrieve.  
**Why:** Abstract queries don't lexically match ancient verses. HyDE bridges the gap.  
**Feasibility:** Medium. 1 day.

---

### TIER 4 — Mobile (Phase 6, after V1 web is validated)

- React Native (Expo) — reuses all backend APIs
- Push notifications for daily wisdom
- Offline cache for bookmarked verses
- Voice input
- Everything from Tier 1-3 available on mobile

**Design principle (starts now):** Every API response, every DB schema, every UI component is designed mobile-first. No desktop-only patterns.

---

## Database Schema (Supabase PostgreSQL)

```sql
-- Users handled by Supabase Auth

reading_progress (
  user_id UUID, slug TEXT, chapter INT, verse INT,
  updated_at TIMESTAMP, PRIMARY KEY (user_id, slug)
)

bookmarks (
  id UUID PRIMARY KEY, user_id UUID, slug TEXT, scripture TEXT,
  chapter INT, verse INT, note TEXT, created_at TIMESTAMP
)

highlights (
  id UUID PRIMARY KEY, user_id UUID, slug TEXT, scripture TEXT,
  chapter INT, verse INT, selected_text TEXT, color TEXT, note TEXT
)

conversations (
  id UUID PRIMARY KEY, user_id UUID, title TEXT,
  created_at TIMESTAMP, shared BOOLEAN DEFAULT false
)

messages (
  id UUID PRIMARY KEY, conversation_id UUID, role TEXT,
  content TEXT, citations JSONB, mode TEXT, created_at TIMESTAMP
)

feedback_responses (
  id UUID PRIMARY KEY, user_id UUID, conversation_id UUID,
  message_idx INT, rating INT, comment TEXT, created_at TIMESTAMP
)

feedback_books (
  id UUID PRIMARY KEY, user_id UUID, slug TEXT, scripture TEXT,
  rating INT, comment TEXT, created_at TIMESTAMP
)

issue_reports (
  id UUID PRIMARY KEY, user_id UUID, slug TEXT, scripture TEXT,
  chapter INT, verse INT, issue_type TEXT, comment TEXT, created_at TIMESTAMP
)

user_books (
  id UUID PRIMARY KEY, user_id UUID, title TEXT, file_path TEXT,
  status TEXT, chunk_count INT, created_at TIMESTAMP
)

leaderboard_settings (
  user_id UUID PRIMARY KEY, opted_in BOOLEAN, display_name TEXT
)
```

---

## Build Order (Recommended)

```
Week 1:  Contextual re-indexing pipeline + re-embed + eval baseline refresh
Week 2:  Per-user quota + Shareable URLs + chat persistence migration
Week 3:  Q&A feedback + Book feedback + Issue reporting
Week 4:  Highlights + Notes + Select-to-ask + User profile
Week 5:  Chat history/sidebar polish + profile refinements + admin review tools
Week 6:  Deploy to Hetzner VPS + Vercel + Cloudflare (production)
Week 7:  HyDE + retrieval tuning + eval gates
Week 8:  Beta testing with real users, fix what breaks
Post-V1: User-uploaded books, Leaderboard, Mobile app
```

---

## Release Gates (Non-Negotiable)

- Retrieval: eval must be `>= 90%` overall and no regression on direct-scripture queries.
- Backend: full test suite green (`pytest`) before each deploy.
- Frontend: `npm run lint` and `npm run build` green before each deploy.
- Security: no service-role keys in frontend bundles; verify OAuth redirect/domain settings on each environment.
- Data safety: any new Supabase table must include RLS policies before frontend wiring.

---

## What's NOT in Scope (Decisions)

| Idea | Decision | Reason |
|---|---|---|
| Fine-tuning LLM | Post-PMF only | Need 500+ real queries as training signal first |
| Paid tier | Never (locked) | Core product promise |
| Social features (follow, share collections) | Post-V1 | Needs user base first |
| Sanskrit voice TTS | Post-V1 | High complexity, low V1 priority |
| Real-time Groq API quota check | Not feasible | Groq doesn't expose remaining quota via API; we track internally |
