# AntarDarshan — Data Admin Reference

> **Who this is for:** The product admin (you). This is the complete reference for
> all corpus data tasks — initial setup, adding books, removing books, re-indexing,
> backups, and troubleshooting. Keep this open whenever doing data work.

---

## 1. Architecture at a glance

```
corpus/raw/          Raw text files (TXT/plain)  — never committed to git
corpus/processed/    Parsed JSON chunks           — never committed to git
Qdrant (local)       Vector index (dense+sparse)  — stored in qdrant_data/ on VPS
CorpusIndex          In-memory read-index         — loaded at backend startup from processed/
Supabase             User data only               — NO corpus data here
```

**What lives where in production:**

| Data | Location | Notes |
|---|---|---|
| Raw text files | `corpus/raw/` on VPS | Source of truth for parsing |
| Parsed JSON chunks | `corpus/processed/` on VPS | Output of parsing step |
| Qdrant vectors | `qdrant_data/` on VPS | Powers RAG search |
| Reading library index | In-memory at startup | Built from `corpus/processed/` |
| Book metadata | `corpus/processed/*.json` | Embedded in each JSON file |

---

## 2. How to get to the VPS for data tasks

```bash
# SSH into your Hetzner VPS
ssh root@YOUR_VPS_IP

# Go to the project directory
cd /path/to/antardarshan

# Activate Python environment
source .venv/bin/activate

# Confirm everything is running
python -m ingestion.admin status
```

You are now ready to do any data operation.

---

## 3. Check current index status

This is the first command to run before any data operation.

```bash
python -m ingestion.admin status
```

Output example:
```
============================================================
AntarDarshan — Index Status
============================================================
Processed JSON files: 44
Total chunks in JSON: 19278
Qdrant points:        19278
Status: ✅ In sync

Scripture                    Chunks
-------------------------------------
  Bhagavad Gita               240
  Dhammapada                  423
  ...
```

**Red flags to watch:**
- `Status: ⚠️ Out of sync` → run `python -m ingestion.admin verify` to see details
- Qdrant points < JSON chunks → re-embed the affected scripture
- Qdrant points > JSON chunks → orphaned vectors; run `remove` then re-`add`

---

## 4. Full ingestion from scratch (initial setup or rebuild)

Use this when setting up a new VPS or if the index is corrupted and needs a full rebuild.

### Step 1 — Ensure raw files are present
```bash
ls corpus/raw/        # should show 44+ .txt files
```

If missing, you need to re-download the corpus. Raw files are not in git (too large).
Contact yourself or restore from backup (see section 9).

### Step 2 — Parse all raw files into JSON chunks
```bash
python -m ingestion.process_all
```
This takes 5-10 minutes. Output goes to `corpus/processed/`.

### Step 3 — Start Qdrant
```bash
docker start qdrant-antardarshan
# Wait ~5 seconds for it to be ready
curl -s http://localhost:6333/health
```

### Step 4 — Embed all chunks and load into Qdrant
```bash
EMBED_MODEL=BAAI/bge-m3 python -m ingestion.embed_and_load
```
This takes 30-60 minutes on first run (embedding 19k+ chunks on CPU).

### Step 5 — Verify
```bash
python -m ingestion.admin verify
# Should show: ✅ In sync, 19278 points
```

### Step 6 — Start the backend
```bash
./start.sh
```

**After this:** All 44 scriptures are indexed, library is populated, RAG search works.

---

## 5. Adding a new book (incremental — existing data untouched)

### What you need first
- A clean plaintext file of the book (`.txt`)
- Book metadata: scripture name, tradition, translator, year
- Whether the text is clean enough for the reading library (`--readable` flag)

### Supported traditions
`hindu_vedanta`, `hindu_yoga`, `buddhist`, `jain`, `sikh`, `sant_bhakti`

### Step-by-step

```bash
# Step 1: Copy raw file to corpus
cp /path/to/yoga_vasistha.txt corpus/raw/yoga-vasistha.txt

# Step 2: Add to index (parses + embeds + loads into Qdrant)
python -m ingestion.admin add corpus/raw/yoga-vasistha.txt \
  --scripture "Yoga Vasistha" \
  --tradition hindu_vedanta \
  --translator "Venkatesananda" \
  --year 1984 \
  --readable
# Remove --readable if OCR quality is poor (text will be RAG-only, not in reading library)

# Step 3: Verify
python -m ingestion.admin verify

# Step 4: Restart backend (required to reload CorpusIndex for reading library)
./start.sh
```

**What updates immediately (no restart needed):**
- ✅ RAG search can find the new book
- ✅ AI answers can cite it

**What needs the restart to update:**
- Reading library list and count
- Corpus stats on home page
- `python -m ingestion.admin status` already shows the new count

### Choosing `--readable` vs not

| Flag | When to use | Result |
|---|---|---|
| `--readable` | Clean, well-formatted text | Shows in reading library, AI cites with clickable links |
| (omit) | OCR artifacts, poor formatting | AI can cite it but it won't appear in /library |

**Quick OCR quality check before deciding:**
```bash
head -100 corpus/raw/your-book.txt
# Look for: garbled characters, ??? sequences, missing spaces between words
```

---

## 6. Removing a book (incremental — other books untouched)

```bash
# Step 1: Remove from Qdrant + delete processed JSON
python -m ingestion.admin remove --scripture "Yoga Vasistha"
# Prompts for confirmation. Type 'yes' to proceed.

# Step 2: Verify it's gone
python -m ingestion.admin verify

# Step 3: Restart backend
./start.sh
```

**After restart:**
- Book disappears from library
- AI can no longer cite it
- Chunk/scripture counts decrease
- Any user bookmarks on that book remain in Supabase (harmless — they'll just 404 if clicked)

---

## 7. Re-indexing a book (update existing)

Use when you have a better/corrected version of an existing book.

```bash
# Step 1: Remove old version
python -m ingestion.admin remove --scripture "Bhagavad Gita"

# Step 2: Add new version
python -m ingestion.admin add corpus/raw/bhagavad-gita-new.txt \
  --scripture "Bhagavad Gita" \
  --tradition hindu_vedanta \
  --translator "Georg Feuerstein" \
  --year 2011 \
  --readable

# Step 3: Verify
python -m ingestion.admin verify

# Step 4: Restart
./start.sh
```

Or use the shortcut:
```bash
python -m ingestion.admin reindex --scripture "Bhagavad Gita"
# Then add with the new file
```

---

## 8. Cross-check and repair

### Verify Qdrant ↔ JSON are in sync
```bash
python -m ingestion.admin verify
```

Shows any scripture where Qdrant count ≠ JSON count.

### Fix a specific out-of-sync scripture
```bash
python -m ingestion.admin remove --scripture "Manu Smriti"
python -m ingestion.admin add corpus/raw/manu-smriti.txt \
  --scripture "Manu Smriti" \
  --tradition hindu_vedanta \
  --translator "G. Bühler" \
  --year 1886
```

### Full integrity check (eval pipeline)
After any major change, run the eval suite to confirm retrieval quality hasn't regressed:
```bash
python -m eval.run_eval
# Target: ≥90% pass rate on the 25 benchmark queries
```

---

## 9. Backup and restore

### Backup Qdrant data
The entire Qdrant index lives in `qdrant_data/` on the VPS.

```bash
# On VPS — create a backup
tar -czf qdrant-backup-$(date +%Y%m%d).tar.gz qdrant_data/
# Transfer to local machine or S3
scp root@YOUR_VPS_IP:~/qdrant-backup-*.tar.gz ./backups/
```

**Recommended:** Back up weekly. The corpus changes infrequently so daily isn't needed.

### Restore Qdrant from backup
```bash
# Stop Qdrant
docker stop qdrant-antardarshan

# Replace data directory
rm -rf qdrant_data/
tar -xzf qdrant-backup-20260625.tar.gz

# Start Qdrant
docker start qdrant-antardarshan
```

### Backup processed JSON (lighter weight)
```bash
tar -czf corpus-processed-$(date +%Y%m%d).tar.gz corpus/processed/
```
This is much smaller than the Qdrant backup and restores in seconds (you'd still need to re-embed if Qdrant is gone, but having processed/ saves the parsing step).

---

## 10. Corpus file format reference

Each file in `corpus/processed/` is a JSON with this structure:
```json
{
  "scripture": "Bhagavad Gita",
  "slug": "bhagavad-gita",
  "tradition": "hindu_vedanta",
  "translator": "Edwin Arnold",
  "year": 1885,
  "license_tier": "public_domain",
  "readable": true,
  "total_chapters": 18,
  "chunks": [
    {
      "chunk_id": "bhagavad-gita-1-1",
      "scripture": "Bhagavad Gita",
      "chapter": 1,
      "verse": 1,
      "text": "Dhritirashtra said...",
      "chunk_type": "verse",
      "contextual_prefix": ""
    }
  ]
}
```

**Key fields:**
- `readable: true` → shows in `/library` reading page
- `readable: false` → RAG-only (AI can cite it, can't read it in the UI)
- `slug` → used in URLs: `/read/{slug}/{chapter}`
- `chunk_type`: `"verse"` (boxed cards) or `"prose"` (flowing book layout)

---

## 11. Supported traditions and their colors

| Key | Display name | Color variable |
|---|---|---|
| `hindu_vedanta` | Vedanta | `--color-vedanta` |
| `hindu_yoga` | Yoga | `--color-yoga` |
| `buddhist` | Buddhist | `--color-buddhist` |
| `jain` | Jain | `--color-jain` |
| `sikh` | Sikh | `--color-sikh` |
| `sant_bhakti` | Sant/Bhakti | `--color-bhakti` |

---

## 12. Production checklist for any corpus change

Before any data operation in production:

- [ ] `python -m ingestion.admin status` — confirm current state
- [ ] Test your raw file locally first before putting on the VPS
- [ ] Back up `qdrant_data/` if doing a large change
- [ ] Run the operation
- [ ] `python -m ingestion.admin verify` — confirm in sync
- [ ] `./start.sh` — restart backend
- [ ] Open `localhost:8000/api/stats` and confirm chunk count updated
- [ ] Do a test search on the new/removed book
- [ ] If adding: do a test query that should cite the new book

---

## 13. Common issues and fixes

| Issue | Cause | Fix |
|---|---|---|
| Book not appearing in library | Missing `--readable` flag | Re-add with `--readable` |
| AI not citing new book | Qdrant didn't get updated | `verify` + restart Qdrant if needed |
| `Out of sync` warning | Partial failure during add/remove | Re-run the add/remove command |
| `Qdrant not running` | Docker container stopped | `docker start qdrant-antardarshan` |
| Book appears in RAG but not library | `readable: false` in JSON | Re-index with `--readable` |
| Chunk count looks wrong | Parsing error | Check the processed JSON manually |
| `/api/stats` shows old count | Backend not restarted | `./start.sh` |

---

## 14. Quick reference card

```
# See everything
python -m ingestion.admin status

# Add a book
python -m ingestion.admin add corpus/raw/<file>.txt \
  --scripture "Name" --tradition <tradition> \
  --translator "Name" --year YYYY [--readable]

# Remove a book
python -m ingestion.admin remove --scripture "Name"

# Check sync
python -m ingestion.admin verify

# Run eval after changes
python -m eval.run_eval

# Restart backend (always after corpus change)
./start.sh
```

---

*Last updated: Jun 25, 2026*
