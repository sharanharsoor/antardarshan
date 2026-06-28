# AntarDarshan — Production Checklist

> Complete these in order. Nothing is optional.

---

## 1. Domain (Day 1)

- [ ] Buy `antardarshan.com` (or variant) on [Cloudflare Registrar](https://www.cloudflare.com/products/registrar/) — ~$10/year
- [ ] Add domain to Cloudflare DNS (automatic when bought via Registrar)

---

## 2. Secrets Rotation (before any public access)

- [ ] Rotate `GROQ_API_KEY` — new key at console.groq.com
- [ ] Rotate `SUPABASE_SERVICE_KEY` — new key at supabase.com > Settings > API
- [ ] Set `CRON_SECRET` to a random 32-char string
- [ ] Verify `.env` on VPS has new values, old values deleted everywhere

---

## 3. Hetzner VPS Setup

```bash
# Recommended: CX22 (2 vCPU, 4GB RAM, 40GB SSD) — $6/month
# Or CPX21 (3 vCPU, 4GB RAM) for slightly more CPU headroom
```

- [ ] Create server at [hetzner.com/cloud](https://www.hetzner.com/cloud) — Ubuntu 24.04 LTS
- [ ] SSH in, clone repo, copy `.env` with production values
- [ ] Install Docker: `apt install docker.io docker-compose`
- [ ] Start Qdrant with persistent volume:
  ```bash
  docker run -d --name qdrant-prod \
    --restart always \
    -p 6333:6333 \
    -v /opt/qdrant_data:/qdrant/storage \
    qdrant/qdrant
  ```
- [ ] Run full corpus ingestion on VPS (takes ~45 min):
  ```bash
  source .venv/bin/activate
  python -m ingestion.process_all
  python -m ingestion.embed_and_load --mode prod
  python -m ingestion.admin verify
  ```
- [ ] Start backend with Gunicorn (4 workers on VPS, no Metal crash):
  ```bash
  GUNICORN_WORKERS=4 BGE_FP16=true ./start.sh
  # or directly:
  EMBED_MODEL=BAAI/bge-m3 BGE_FP16=true \
    gunicorn backend.app:app \
    -w 4 -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 --timeout 120
  ```
- [ ] Run eval on VPS: `python -m eval.run_eval` — must pass ≥90%

---

## 4. Cloudflare Setup

- [ ] Add VPS IP to Cloudflare DNS:
  - `A antardarshan.com → Vercel` (for frontend — set in Vercel dashboard)
  - `A api.antardarshan.com → <VPS IP>` — proxy ON (orange cloud)
- [ ] Enable "Full (strict)" SSL mode in Cloudflare SSL/TLS settings
- [ ] Enable Cloudflare Rate Limiting on free plan (basic WAF rules)
- [ ] Install Cloudflare Tunnel on VPS for secure backend exposure:
  ```bash
  # Alternative to exposing port 8000 directly
  cloudflared tunnel create antardarshan-api
  ```

---

## 5. Vercel Frontend Deploy

- [ ] Import GitHub repo at [vercel.com](https://vercel.com)
- [ ] Set environment variables in Vercel dashboard:
  ```
  NEXT_PUBLIC_API_URL=https://api.antardarshan.com
  NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
  ```
- [ ] Add custom domain `antardarshan.com` in Vercel → Domains
- [ ] Verify `next.config.js` has no localhost hardcodes

---

## 6. Supabase Production Config

- [ ] Add `https://antardarshan.com` to Supabase Auth > URL Configuration > Site URL
- [ ] Add `https://antardarshan.com/auth/callback` to Redirect URLs
- [ ] Add `https://api.antardarshan.com` to CORS allowed origins

---

## 7. Backend CORS Tightening

Change in `backend/app.py`:
```python
# Replace allow_origins=["*"] with:
allow_origins=[
    "https://antardarshan.com",
    "https://www.antardarshan.com",
    # remove localhost entries for production
]
```

---

## 8. LangFuse Production Config

- [ ] Set `LANGFUSE_LOG_CONTENT=false` in production `.env`
- [ ] Verify traces appearing in LangFuse dashboard after first query

---

## 9. Final Verification (pre-launch)

- [ ] `python -m ingestion.admin verify` — all counts in sync
- [ ] `python -m eval.run_eval` — 25/25 on production VPS
- [ ] Load test from a remote machine: `locust -f tests/load_test.py --host https://api.antardarshan.com`
- [ ] Sign in with Google end-to-end on production domain
- [ ] Ask 5 questions, check citations, check highlights save
- [ ] Check LangFuse traces appearing
- [ ] Check Supabase table row counts growing correctly

---

## 10. Go Live

- [ ] Remove `DISABLE_RATE_LIMIT` if set
- [ ] Announce on LinkedIn/Twitter
- [ ] Monitor Groq usage dashboard for first 48h

---

*Last updated: Jun 28, 2026*
