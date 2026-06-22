# AntarDarshan — UI/UX Design Plan

> **Living document.** All LLMs + user collaborate here before building the frontend.  
> Last updated: 2026-06-18 by Claude Opus 4 (v3 — fixed 2 blockers + 6 medium/minor issues from Sonnet 4.6 review)

---

## 1. Pages & Routes

| Route | Page | Purpose |
|-------|------|---------|
| `/` | Landing | Hero + search bar + daily wisdom + tradition cards |
| `/ask` | Q&A Chat | Multi-turn conversation with citations |
| `/library` | Scripture Library | Browse all texts by tradition |
| `/read/{slug}` | Chapter List (Table of Contents) | Pick which chapter to read |
| `/read/{slug}/{chapter}` | Chapter Reading (full scroll) | All verses in a chapter, scrollable |
| `/read/{slug}/{chapter}/{verse}` | Deep-link to Verse | Same chapter page, auto-scrolls to verse + highlights |
| `/about` | About | Traditions, sources, privacy, team |

**Route change from v1:** Reading mode now has 3 levels (book → chapter → verse) instead of jumping directly to a single verse. This is how Kindle/Readwise works — you see the table of contents, pick a chapter, and scroll through it.

---

## 2. Landing Page (`/`)

```
┌─────────────────────────────────────────────────────────────────┐
│  AntarDarshan — अन्तर्दर्शन                          [☀/🌙]      │
│  "Inner Vision Through Ancient Wisdom"                           │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Ask anything about Indian philosophy...                    │ │
│  │  [_______________________________________________] [Ask →]  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Example questions:                                               │
│  • "What does the Gita say about duty?"                          │
│  • "I'm going through a difficult time"                          │
│  • "How does Vedanta differ from Buddhism on the self?"          │
│                                                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Vedanta  │  │ Buddhist │  │  Yoga    │  │  Jain    │        │
│  │ {n} texts│  │ {n} text │  │ {n} text │  │ (coming) │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                   │
│  Daily Wisdom: "You are the one witness of everything,           │
│  and are always totally free." — Ashtavakra Gita 1.7             │
│                                                                   │
│  [Browse Library →]     [Start Reading →]                         │
│                                                                   │
│  ─── Free forever. {total_verses} verses indexed. No ads. ───    │
└─────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Search bar is the hero — submits redirect to `/ask` (not inline results)
- Example queries show all 3 modes (citation, well-being, comparison)
- Tradition cards show corpus breadth
- Daily wisdom (no LLM cost — deterministic `hash(date) % corpus_size`)
- "Free forever" positioning below the fold
- Dark/light mode toggle in header (☀/🌙)

---

## 3. Q&A Chat (`/ask`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← AntarDarshan    [New Chat]              Queries: ● available  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─ User ──────────────────────────────────────────────────────┐ │
│  │ I lost my father recently and feel lost.                    │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─ AntarDarshan ─────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │ I understand this is a deeply painful time. The ancient     │ │
│  │ texts speak to grief with both compassion and clarity.      │ │
│  │                                                             │ │
│  │ Krishna teaches Arjuna:                                     │ │
│  │                                                             │ │
│  │ > "Thou grievest where no grief should be! The wise in     │ │
│  │ > heart mourn not for those that live, nor those that die." │ │
│  │                                                             │ │
│  │ — Bhagavad Gita, Ch.2, Stanza 6 (Edwin Arnold, 1885)      │ │
│  │   [Read full chapter →]                                     │ │
│  │                                                             │ │
│  │ The Katha Upanishad, a dialogue with Death itself:          │ │
│  │                                                             │ │
│  │ > "The Self is not born, nor does it die..."               │ │
│  │ — Katha Upanishad, Section 2, Verse 18 (Müller, 1884)      │ │
│  │   [Read full chapter →]                                     │ │
│  │                                                             │ │
│  │ ┌─────┐ ┌─────┐                                            │ │
│  │ │ 👍  │ │ 👎  │  [Citation wrong?]                         │ │
│  │ └─────┘ └─────┘                                            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─ User ──────────────────────────────────────────────────────┐ │
│  │ Tell me more about what the Katha Upanishad says            │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  (multi-turn: session continues with context)                    │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│  [_______________________________________________] [Send →]      │
│  Mode: well_being | Session active                               │
└─────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Dark mode toggle in header (same as all pages — lives in Header.tsx)
- Query availability indicator top-right: green dot (available), yellow (>80% daily budget used), red (limit reached). NOT per-user counts — budget is org-level shared.
- Multi-turn supported — session_id persists in sessionStorage
- Citations are clickable → opens reading mode at that verse
- Thumbs up/down on every response (anonymous analytics)
- "Citation wrong?" flag for data quality improvement
- Mode auto-detected and shown subtly
- "New Chat" button calls `DELETE /api/session/{id}` then clears state
- **Pre-fill from reading mode:** reads `?prefill=` URL search param on mount, sets as initial input
- Loading: typing indicator animation. Error: "Could not reach server — tap to retry."

---

## 4. Scripture Library (`/library`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← AntarDarshan         Scripture Library              [☀/🌙]    │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ Continue reading: Ashtavakra Gita, Ch.5 v.3    [Resume →]  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Filter: [All] [Vedanta] [Buddhist] [Yoga] [Modern Teachers]    │
│                                                                   │
│  ── Vedanta ─────────────────────────────────────────────────    │
│                                                                   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐    │
│  │ Bhagavad Gita  │  │ Ashtavakra     │  │ Katha          │    │
│  │ ────────────── │  │ Gita           │  │ Upanishad      │    │
│  │ 18 chapters    │  │ ────────────── │  │ ────────────── │    │
│  │ 240 stanzas    │  │ 20 chapters    │  │ 6 sections     │    │
│  │ Arnold, 1885   │  │ 296 verses     │  │ 119 verses     │    │
│  │                │  │ Richards, 1994 │  │ Müller, 1884   │    │
│  │ [Read →]       │  │ [Read →]       │  │ [Read →]       │    │
│  └────────────────┘  └────────────────┘  └────────────────┘    │
│                                                                   │
│  + 6 more Upanishads...                                          │
│                                                                   │
│  ── Buddhist ────────────────────────────────────────────────    │
│  ── Yoga ────────────────────────────────────────────────────    │
│  ── Modern Teachers ─────────────────────────────────────────    │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- "Continue reading" banner at top (if user has bookmarked progress, requires login)
- Filter by tradition (tab-style)
- Each scripture card: name, translator, year, chapter/verse count
- "Read →" links to `/read/{slug}` (chapter list, not directly to verse 1)
- Only shows `ingestion_status = approved` sources (legal gate)
- Mobile: cards stack vertically, full-width
- Loading: skeleton cards (grey pulsing rectangles). Error: "Could not load library — tap to retry."

---

## 5. Chapter List / Table of Contents (`/read/{slug}`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Library    Ashtavakra Gita    John Richards, 1994   [☆ Save] │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─ Progress (chapter-based) ─────────────── 25% ─────────────┐ │
│  │ ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Tradition: Vedanta (Advaita)                                    │
│  296 verses across 20 chapters                                   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  Ch 1.  Instruction on Self-Knowledge    (20 verses)  [→]  │ │
│  │  Ch 2.  Joy of Self-Realization          (25 verses)  [→]  │ │
│  │  Ch 3.  Test of Self-Knowledge           (14 verses)  [→]  │ │
│  │  Ch 4.  Dissolution of the World         (6 verses)   [→]  │ │
│  │  Ch 5.  Nature of Dissolution ← READING HERE         [→]  │ │
│  │  Ch 6.  The Higher Knowledge             (4 verses)   [→]  │ │
│  │  Ch 7.  Tranquility                      (5 verses)   [→]  │ │
│  │  ...                                                        │ │
│  │  Ch 18. Peace                            (100 verses) [→]  │ │
│  │  Ch 19. Repose in the Self               (8 verses)   [→]  │ │
│  │  Ch 20. Liberation in Life               (14 verses)  [→]  │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  [Ask about this text →]                                          │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Key elements:**
- Progress bar (chapter-based: `current_chapter / total_chapters` — same as reading mode)
- Current reading position highlighted ("← READING HERE")
- Chapter names where available (from `chapter_name` field)
- Verse count per chapter
- "Ask about this text →" links to `/ask` pre-filled with the scripture name
- Back to library navigation
- **Current position marker** ("← READING HERE") comes from `GET /api/bookmarks/resume/{scripture}` — shown only when logged in, null otherwise. Page makes 2 API calls: one for chapters, one for resume position.
- Loading: skeleton list items. Error: "Could not load — tap to retry."

---

## 6. Reading Mode — Full Chapter Scroll (`/read/{slug}/{chapter}`)

```
┌─────────────────────────────────────────────────────────────────┐
│  ← Contents   Ashtavakra Gita   Ch.1 / 20   [☆ Bookmark]       │
├─── Progress: ████████████░░░░░░░░░░░░ 5% ──────────────────────┤
│                                                                   │
│  Chapter 1: Instruction on Self-Knowledge                        │
│  Tradition: Vedanta (Advaita)                                    │
│                                                                   │
│  Speaker: Janaka                                                 │
│                                                                   │
│  ┌─ 1.1 ──────────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  How is knowledge to be acquired? How is liberation to be   │ │
│  │  attained? And how is dispassion to be reached? Tell me     │ │
│  │  this, sir.                                                  │ │
│  │                                                             │ │
│  │  [Explain this →]  [Ask about this →]                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Speaker: Ashtavakra                                             │
│                                                                   │
│  ┌─ 1.2 ──────────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  If you are seeking liberation, my son, shun the objects    │ │
│  │  of the senses like poison. Practise tolerance, sincerity,  │ │
│  │  compassion, contentment and truthfulness like nectar.       │ │
│  │                                                             │ │
│  │  [Explain this →]  [Ask about this →]                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─ 1.3 (highlighted — deep-linked) ─────────────────────────┐ │
│  │                                                             │ │
│  │  You are neither earth, water, fire, air or even ether.     │ │
│  │  For liberation know yourself as consisting of               │ │
│  │  consciousness, the witness of these.                        │ │
│  │                                                             │ │
│  │  ┌─ AI Explanation (expanded) ────────────────────────────┐ │ │
│  │  │ This verse teaches the fundamental Advaita insight:    │ │ │
│  │  │ you are not the five elements (pancha-bhuta). You are  │ │ │
│  │  │ consciousness itself — the witness (sakshi).           │ │ │
│  │  │                                                        │ │ │
│  │  │ Compare: Katha Upanishad 2.20 — "The Self, smaller    │ │ │
│  │  │ than small, greater than great..."                     │ │ │
│  │  └────────────────────────────────────────────────────────┘ │ │
│  │                                                             │ │
│  │  [Explain this →]  [Ask about this →]                       │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─ 1.4 ──────────────────────────────────────────────────────┐ │
│  │  ...                                                        │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  (... all 20 verses scrollable ...)                              │
│                                                                   │
├─────────────────────────────────────────────────────────────────┤
│  [← Previous (disabled)] Ch 1 of 20         [Next: Ch.2 →]     │
│                                                                   │
│  Share: antardarshan.com/read/ashtavakra-gita/1/3     [Copy 🔗] │
└─────────────────────────────────────────────────────────────────┘
```

**Key changes from v1:**
- **Full chapter loads as scrollable page** (not single-verse pagination)
- Deep-link URL (`/read/{slug}/{ch}/{verse}`) loads same page + auto-scrolls to verse + highlights it
- Progress bar at top (thin, unobtrusive)
- **"Ask about this →"** button on every verse — pre-fills `/ask` with the verse text
- "Explain this →" still expands inline (no navigation away)
- All verses visible — the user scrolls like reading a book
- Tradition badge once in chapter header, not per-verse (reduces noise)

**"Ask about this →" mechanism:**
- Button navigates to: `/ask?prefill={encodeURIComponent(verse.text.slice(0, 200))}`
- The `/ask` page reads `searchParams.prefill` on mount → sets as initial chat input
- User sees their input pre-filled, can edit before sending
- This is the cross-page state transfer pattern (URL params, no sessionStorage needed)

**Progress calculation (V1):**
- Progress = `current_chapter / total_chapters` (chapter-based, simple)
- Updated when user navigates to a new chapter
- Displayed as thin bar under header + percentage text
- Verse-based precision (verses_seen / total) deferred to V2

**Loading/Error states:**
- Loading: skeleton verse blocks (3 grey pulsing rectangles)
- Error: "Could not load chapter — tap to retry" with retry button
- Explain loading: small spinner inside the expand area

**Share URL logic:**
- Verse texts: share URL = `/read/{slug}/{chapter}/{verse}` (full deep link)
- Prose texts: share URL = `/read/{slug}/{chapter}` (no verse segment)
- `ShareButton` receives `includeVerse: boolean` prop based on `chunk_type`

**For prose texts (Vivekananda):**
- No verse numbers shown (chunk_type = "prose")
- Paragraphs flow naturally
- URL: `/read/vivekananda-jnana-yoga/1` (chapter only, no verse in URL)
- "Explain this" still works per-paragraph
- Share URL omits verse segment

---

## 7. Design System

### Colors — Light Mode (default)

```
Background:       #FDFCFA (warm off-white)
Surface:          #F8F5F0 (card backgrounds)
Text primary:     #2D2A26 (warm near-black)
Text secondary:   #6B6560 (muted)
Accent:           #C4854C (saffron/amber)
Accent hover:     #A66B35 (darker saffron)
Citation bg:      #F5F0EB (warm tan for blockquotes)
Border:           #E8E2DA (subtle warm border)
Error:            #C44C4C
Success:          #4C8A5B
```

### Colors — Dark Mode (V1, user decision)

```
Background:       #1A1816 (warm dark)
Surface:          #252220 (card backgrounds)
Text primary:     #E8E2DA (warm off-white)
Text secondary:   #9B9590 (muted light)
Accent:           #D4A574 (lighter saffron for contrast)
Accent hover:     #E8B88A
Citation bg:      #2A2624 (dark tan)
Border:           #3A3530
```

**Implementation:** All colors as CSS custom properties (`--color-bg`, `--color-text`, etc.) in a `:root` and `[data-theme="dark"]` selector. Toggle stored in localStorage. System preference detected on first visit.

### Tradition badges (same in both themes)
```
hindu_vedanta:  #8B6914 / dark: #C4A04C (gold)
buddhist:       #5B7E3D / dark: #8BB86A (green)
hindu_yoga:     #6B4C8A / dark: #9B7CB8 (purple)
jain:           #2E7A5A / dark: #5BAA8A (teal)
sikh:           #2E5A88 / dark: #5B8AB8 (blue)
sant_bhakti:    #8A4C6B / dark: #B87C9B (rose)
```

### Typography

```
Headings:    Playfair Display (serif, classical dignity)
Body:        Inter (clean, highly readable at all sizes)
Quotes:      Georgia or Noto Serif (for scripture citations)
Sanskrit:    Noto Serif Devanagari (headers, verse numbers in traditional notation)
Mono:        JetBrains Mono (verse numbers, debug info)
```

### Sizes

```
Body text:       16px (mobile), 18px (desktop)
Verse text:      18px (mobile), 20px (desktop) — larger for readability
Headings:        24-36px
Line height:     1.6 (body), 1.8 (verse text — needs breathing room)
Max content:     720px (reading), 1080px (library grid)
Card spacing:    16px (mobile), 24px (desktop)
Tap targets:     44px minimum (mobile accessibility)
```

### Feel

```
- calm.com meets notion.so
- Generous whitespace (Indian texts need space to breathe)
- No animations or distractions (subtle transitions only: 150ms ease)
- No ads, no popups, no cookie banners (free product, no tracking)
- Mobile-first (India = 95% mobile internet)
- Dark mode: V1, CSS custom properties, system-preference on first visit
- Devanagari script: show for product name, scripture names in headers
```

---

## 8. Tech Stack (Frontend)

```
Framework:      Next.js 14+ (App Router, server components)
Styling:        Tailwind CSS 3+ (with CSS custom properties for theme)
Components:     shadcn/ui (accessible, clean, customizable)
State:          React hooks + sessionStorage (session_id) + localStorage (theme only)
Icons:          Lucide React
Fonts:          Google Fonts (Playfair Display, Inter, Noto Serif Devanagari)
Deploy:         Vercel (free tier)
API calls:      fetch() to Hetzner VPS backend
Auth:           Supabase Auth (reading mode bookmarks only)
Theme:          next-themes (handles dark/light + system preference)
```

---

## 9. Component Breakdown

```
app/
├── layout.tsx              ← root layout (fonts, nav, theme provider, footer)
├── page.tsx                ← landing page (/)
├── ask/
│   └── page.tsx            ← Q&A chat (/ask) — reads ?prefill= search param for pre-filled input
├── library/
│   └── page.tsx            ← scripture library (/library)
├── read/
│   └── [slug]/
│       ├── page.tsx        ← chapter list / table of contents (/read/{slug})
│       └── [chapter]/
│           ├── page.tsx    ← full chapter reading view (/read/{slug}/{ch})
│           └── [verse]/
│               └── page.tsx  ← SSR per-verse deep link (renders same chapter view
│                               with highlightVerse={verse} prop, auto-scrolls)
│                               Sets canonical to parent chapter page (SEO: chapter is indexed, not each verse).
└── about/
    └── page.tsx            ← about page

components/
├── chat/
│   ├── ChatInput.tsx       ← message input with send button
│   ├── ChatMessage.tsx     ← single message bubble (user or AI)
│   ├── CitationCard.tsx    ← clickable citation block → links to reading mode
│   └── QueryStatus.tsx     ← global availability indicator (green/yellow/red dot from GET /api/quota-status)
├── library/
│   ├── ScriptureCard.tsx   ← scripture tile in library grid
│   ├── TraditionFilter.tsx ← filter tabs (All, Vedanta, Buddhist, Yoga...)
│   ├── LibraryGrid.tsx     ← responsive grid layout
│   └── ContinueReading.tsx ← "Resume reading" banner (requires auth)
├── reading/
│   ├── ChapterList.tsx     ← table of contents for a scripture
│   ├── ChapterListItem.tsx ← single chapter row: number, name, verse count, progress dot, "← HERE"
│   ├── VerseBlock.tsx      ← single verse with explain + ask buttons (verse_type texts)
│   ├── ProseBlock.tsx      ← paragraph for prose texts (no verse numbers, chunk_type="prose")
│   ├── ExplainPanel.tsx    ← inline AI explanation (expandable, inline not modal)
│   ├── ChapterNav.tsx      ← prev/next chapter controls (receives hasPrev/hasNext booleans, disabled state when at boundary)
│   ├── ProgressBar.tsx     ← thin reading progress indicator (chapter-based in V1)
│   ├── BookmarkButton.tsx  ← requires auth, saves to Supabase (UPSERT for progress)
│   ├── AskAboutButton.tsx  ← "Ask about this verse" → navigates to /ask?prefill={text}
│   └── SkeletonVerse.tsx   ← loading placeholder (3 grey pulsing blocks)
├── shared/
│   ├── Header.tsx          ← nav bar + dark mode toggle
│   ├── ThemeToggle.tsx     ← light/dark mode switch
│   ├── DailyWisdom.tsx     ← daily verse card
│   ├── TraditionBadge.tsx  ← colored badge per tradition
│   ├── ShareButton.tsx     ← copy link / WhatsApp / Twitter
│   └── SpeakerIcon.tsx     ← placeholder for future TTS (hidden in V1 CSS)
└── ui/                     ← shadcn/ui base components
```

---

## 10. API Contract (Frontend → Backend)

```typescript
// ─── Q&A ───────────────────────────────────────────────────────
POST /api/query
  Request:  { query: string, session_id?: string, top_k?: number }
  Response: { answer: string, mode: string, citations: Citation[],
              session_id: string, latency_ms: number }

// ─── Library ───────────────────────────────────────────────────
GET /api/library
  Response: { scriptures: Scripture[] }

GET /api/library/{scripture}
  Response: { scripture: Scripture, chapters: ChapterSummary[] }
  // Powers the table of contents page. One call, no per-chapter fetching.

GET /api/library/{scripture}/{chapter}
  Response: { scripture: string, chapter: number, verses: Verse[] }
  // chapter_info (name, total_verses) derivable client-side from verses.length
  // and verses[0].chapter_name — no extra backend field needed for V1

GET /api/library/{scripture}/{chapter}/{verse}
  Response: { verse: Verse, context_verses: Verse[] }
  // Context = surrounding ±2 verses from same chapter

// ─── Reading Mode (Explain) ────────────────────────────────────
POST /api/explain
  Request:  { scripture: string, chapter: number, verse: number }
  Response: { verse: Verse, explanation: string, context_verses: Verse[] }

// ─── Bookmarks (requires Supabase Auth) ────────────────────────
POST /api/bookmarks
  Request:  { scripture: string, chapter: number, verse: number,
              bookmark_type: "progress" | "saved", note?: string }
  Response: { id: string, saved_at: string }

GET /api/bookmarks
  Response: { bookmarks: Bookmark[] }

GET /api/bookmarks/resume/{scripture}
  Response: { chapter: number, verse: number } | null

// ─── Session ───────────────────────────────────────────────────
DELETE /api/session/{session_id}
  Response: { cleared: boolean, session_id: string }

// ─── Quota Status ──────────────────────────────────────────────
GET /api/quota-status
  Response: { status: "available" | "limited" | "exhausted",
              queries_today: number, daily_limit: number }
  // Frontend maps: available=green, limited=yellow (>80%), exhausted=red
  // Backend computes from SQLite query_logs COUNT WHERE date = today

// ─── Health ────────────────────────────────────────────────────
GET /api/health
  Response: { status: string, version: string, active_sessions: number }

// ─── Types ─────────────────────────────────────────────────────
interface Citation {
  scripture: string
  chapter: number
  verse: number
  translator: string
}

interface Scripture {
  scripture: string
  slug: string          // URL-safe: "bhagavad-gita", "ashtavakra-gita", "katha-upanishad"
  tradition: string
  translator: string
  year: number
  total_chapters: number
  total_verses: number
  license_tier: string
}
// Slug derivation rule (backend computes, frontend consumes):
//   slug = scripture.lower().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '')
//   "Bhagavad Gita" → "bhagavad-gita"
//   "Vivekananda - Jnana-Yoga" → "vivekananda-jnana-yoga"
//   Backend returns slug in GET /api/library. Frontend uses it for all /read/{slug} routes.

interface Verse {
  text: string
  scripture: string
  chapter: number
  verse: number
  translator: string
  tradition: string
  themes: string[]
  speaker?: string
  chapter_name?: string
  verse_type: string
  chunk_type: string  // "verse" | "prose"
}

interface ChapterSummary {
  chapter: number
  name?: string         // from chapter_name field in corpus
  verse_count: number
  verse_type: string    // "verse" | "stanza" | "segment" | "prose"
}

interface Bookmark {
  id: string
  scripture: string
  chapter: number
  verse: number
  bookmark_type: "progress" | "saved"
  note?: string
  created_at: string
}
```

---

## 11. Mobile Responsiveness

```
Breakpoints:
  sm:   < 768px   (mobile — single column, bottom input)
  md:   768-1024  (tablet — wider reading column)
  lg:   > 1024    (desktop — centered max-width, elegant margins)

Mobile-first priorities:
  1. Chat input: sticky bottom, always accessible
  2. Verse text: 18px+, generous line-height (1.8)
  3. Touch targets: 44px minimum (Explain, Bookmark, Send buttons)
  4. Library cards: stack vertically, full-width
  5. Share: WhatsApp prominent (Indian users share via WhatsApp)
  6. Reading mode: scrollable chapter, not paginated
  7. Dark mode: respects system preference on first visit
```

---

## 12. User Flows

### Flow 1: New user asks a question
```
Landing (/) → types question → redirected to /ask → sees answer with citations
                                                   → clicks citation → /read/{slug}/{ch} (scrolled to verse)
```

### Flow 2: User browses and reads like a book
```
Landing (/) → [Browse Library] → /library → picks scripture card
           → /read/{slug} (table of contents) → picks chapter
           → /read/{slug}/{ch} (full chapter, scrollable)
           → reads verses → clicks [Explain this] → inline explanation
           → clicks [Ask about this →] → /ask pre-filled with verse
           → wants to save progress → [☆ Bookmark] → prompted to sign up
```

### Flow 3: Shared verse link (organic growth / SEO)
```
Friend shares: antardarshan.com/read/ashtavakra-gita/1/7
           → SSR renders full chapter 1, scrolls to verse 7, highlights it
           → user reads surrounding context → [Ask about this →] → /ask
           → no account needed to view (only to bookmark)
```

### Flow 4: Returning user resumes reading
```
User returns → /library → sees "Continue reading: Ashtavakra Gita Ch.5" banner
           → clicks [Resume →] → /read/ashtavakra-gita/5 (scrolled to last verse)
```

---

## 13. Resolved Design Questions

| Question | Decision | Reasoning |
|----------|----------|-----------|
| Landing search: inline or redirect? | **Redirect to `/ask`** | Landing's job is conversion. Inline results = rebuild chat UI on landing. |
| Dark mode: V1 or V2? | **V1** (user decision) | Build with CSS custom properties from day 1. Use `next-themes`. |
| "Explain this": modal or inline? | **Inline expansion** | Modal breaks reading flow. Inline keeps eye on context. |
| Tradition badges in reading? | **Once in chapter header only** | Per-verse badges = visual noise during focused reading. |
| Audio/TTS? | **Placeholder in V1, active in V2** | Add hidden `SpeakerIcon` component. Activate later. |
| Devanagari? | **Script display in V1, full translation in V2** | Use Noto Serif Devanagari for: product name, scripture names in headers. |
| Verse pagination vs scroll? | **Full chapter scroll** | Kindle/Readwise pattern. Verse pagination feels like Twitter. |

---

## 14. What This Does NOT Include (V2+)

- User profiles / dashboards
- Community features (user-submitted questions)
- Audio/TTS for verses (placeholder in V1)
- Full Hindi/Tamil translation of verses
- Mobile app (React Native — post-web validation)
- Social features (comments on verses)
- Gamification (reading streaks, badges)
- Offline mode / PWA

---

---

## 15. Implementation Notes (Pre-Build Sync)

### API sync with backend

The following endpoints exist in the design contract but **NOT YET in the backend** (`backend/app.py`). They must be implemented before the frontend can integrate:

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /api/health` | Exists | |
| `POST /api/query` | Exists | |
| `GET /api/library` | **NEEDS UPDATE** | Must add `slug` field to each scripture object (computed: `scripture.lower().replace(/[^a-z0-9]+/g, '-')`) |
| `GET /api/library/{scripture}` | **NOT YET** | Add to `backend/app.py` — returns `ChapterSummary[]` from `CorpusIndex` |
| `GET /api/library/{scripture}/{chapter}` | Exists | |
| `GET /api/library/{scripture}/{chapter}/{verse}` | **NOT YET** | Add — returns single verse + context |
| `POST /api/explain` | Exists | |
| `POST /api/bookmarks` | **NOT YET** | Requires Supabase integration |
| `GET /api/bookmarks` | **NOT YET** | Requires Supabase integration |
| `GET /api/bookmarks/resume/{scripture}` | **NOT YET** | Requires Supabase integration |
| `GET /api/quota-status` | **NOT YET** | Add — COUNT from SQLite `query_logs` WHERE date = today, compare against 15,400 daily limit |
| `DELETE /api/session/{session_id}` | Exists | Backend returns `{"cleared": true, "session_id": "..."}` — frontend should check `cleared === true` |

**Action:** Implement missing endpoints in backend BEFORE starting frontend integration. The CorpusIndex already has the data for library endpoints; bookmarks need Supabase tables.

### Prose chunks and verse indexing

Prose chunks (Vivekananda) DO have stable numeric `verse` fields — they are paragraph indices within a chapter (1, 2, 3...). These are synthetic but deterministic (same chunk = same number on every pipeline run). The `POST /api/explain` contract works for prose:

```
POST /api/explain { scripture: "Vivekananda - Jnana-Yoga", chapter: 1, verse: 3 }
```

This returns paragraph 3 of chapter 1. The frontend simply hides the verse number label for `chunk_type = "prose"` — the API contract is the same internally.

### Dynamic corpus numbers (not hardcoded)

The landing page MUST NOT hardcode "12 texts" or "1,972 verses". Instead:
- Call `GET /api/library` on page load (or at build time via Next.js ISR)
- Compute: `scriptures.length` for text count, `sum(s.total_verses)` for verse count
- Display dynamically: "14 texts • 1,972 verses indexed"

### Query counter UX vs. backend reality

The design shows "Simple: 14,391 | Deep: 998" — but the backend does NOT currently track per-user quota. The Groq free tier is org-level (shared across ALL users), not per-user.

**V1 approach (final):** Green/yellow/red dot indicator. On hover/tap, shows tooltip: "X of 15,400 queries used today." No per-user counts — budget is org-level shared.

```
UI:    ● (green dot, pulsing gently)
Hover: "2,140 of 15,400 queries used today"
Red:   "Daily limit reached. Resets at midnight UTC."
```

Frontend calls `GET /api/quota-status` once on page load and every 5 minutes. Maps `status` field directly to dot color.

**Timezone:** Backend computes "today" in UTC (`DATE(created_at) = DATE('now')` in SQLite uses UTC). UI says "resets at midnight UTC." Both aligned.

### Bookmark storage: single source of truth

**Decision: Server-side only (Supabase).** NOT localStorage.

The tech stack line saying `localStorage (theme, bookmarks)` is corrected:
- `localStorage`: theme preference ONLY
- `sessionStorage`: session_id ONLY  
- `Supabase`: bookmarks + reading progress (requires auth)

If user is NOT logged in: no bookmarks, no progress saving. The [Bookmark] button prompts sign-up. There is no "anonymous bookmark in localStorage" — that creates reconciliation complexity with no benefit.

### SEO for verse deep-links

For long chapters (Brihadaranyaka has 234 verses across multiple sections), rendering a full SSR page per verse risks duplicate content. Strategy:

- The `[verse]/page.tsx` route sets `<link rel="canonical" href="/read/{slug}/{chapter}">` pointing to the parent chapter page
- It renders the same chapter content but with `?highlight={verse}` for scroll behavior
- Google indexes the chapter page (canonical), not individual verse pages
- Individual verse URLs still work perfectly for sharing — they just canonicalize to the chapter

### Accessibility requirements

All interactive elements MUST have:
- `aria-label` on icon-only buttons (☀/🌙 = "Toggle dark mode", ☆ = "Bookmark this verse", 👍 = "Helpful", 👎 = "Not helpful")
- Keyboard navigation: all buttons focusable, Enter/Space activates
- Focus visible states (not removed by CSS reset)
- Color contrast: all text meets WCAG AA (4.5:1 ratio) in both light and dark mode
- Screen reader: verse text is in semantic `<article>` elements, citations in `<blockquote cite="...">`

---

*This document is the design contract. All LLMs + user must agree before frontend code is written.*

