# Deployment Guide — D4-Ticket AI

> **Stack:** FastAPI backend on Railway · Next.js frontend on Vercel · PostgreSQL on Railway · File storage on Cloudflare R2
> **Cost:** $0/month (all free tiers)

---

## Prerequisites

- GitHub account with the repo pushed
- Google Cloud Console account (for OAuth + AI Studio)
- Cloudflare account (free, for R2 storage)
- Railway account → [railway.app](https://railway.app)
- Vercel account → [vercel.com](https://vercel.com)

---

## Step 1 — Google OAuth credentials

> These are needed before you can deploy anything, because the backend won't start without them.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or reuse an existing one)
3. Enable the **Google+ API** → APIs & Services → Library → search "Google+ API" → Enable
4. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Application type: **Web application**
6. Name: `D4-Ticket AI`
7. Under **Authorized redirect URIs**, add (you'll update this after Railway deploy):
   ```
   http://localhost:8000/api/v1/auth/callback
   ```
8. Save → copy **Client ID** and **Client Secret** — you'll need them in Railway env vars

---

## Step 2 — Google AI Studio API key (for the AI agent)

1. Go to [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Click **Create API key**
3. Copy the key — you'll set it as `GOOGLE_API_KEY` in Railway

> **Free tier:** 500 requests/day with Gemini 2.5 Flash — more than enough for a demo.
> **Failover:** Set `AI_PROVIDER=openai` and add `OPENAI_API_KEY` to use GPT-4o-mini as a high-availability fallback.

---

## Step 3 — Cloudflare R2 (file storage)

1. Log in to [dash.cloudflare.com](https://dash.cloudflare.com)
2. In the left sidebar → **R2 Object Storage** → **Create bucket**
3. Bucket name: `attachments` (or whatever you set in `STORAGE_BUCKET`)
4. Region: Automatic
5. Click **Create bucket**

**Create API credentials:**

6. In R2 → **Manage R2 API tokens** → **Create API token**
7. Permissions: **Object Read & Write**
8. Specify bucket: select `attachments`
9. Create → copy:
   - **Access Key ID** → `STORAGE_ACCESS_KEY`
   - **Secret Access Key** → `STORAGE_SECRET_KEY`
10. Your R2 endpoint URL (visible on the bucket page):
    ```
    https://<your-account-id>.r2.cloudflarestorage.com
    ```
    → set as `STORAGE_ENDPOINT`

> R2 free tier: 10 GB storage · 1M Class A operations/month · 10M Class B operations/month. No egress fees.

---

## Step 4 — Railway (backend + PostgreSQL)

### 4.1 Create a new Railway project

1. Go to [railway.app](https://railway.app) → **New Project**
2. Select **Deploy from GitHub repo**
3. Authorize Railway to access your GitHub account
4. Select the `D4-ticket-AI` repository

Railway will detect `railway.json` in the root and configure the build automatically.

### 4.2 Add PostgreSQL

1. Inside your Railway project → **+ New** → **Database** → **Add PostgreSQL**
2. Railway creates the database and injects `DATABASE_URL` automatically into your service

> **Important:** Railway's `DATABASE_URL` uses the `postgresql://` scheme. The backend needs `postgresql+asyncpg://`. Set the variable manually in the next step.

### 4.3 Set environment variables

In your Railway backend service → **Variables** tab, add:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<password>@<host>:<port>/<db>` *(Use the **Internal/Private** Database URL from Railway and add `+asyncpg` after `postgresql` for better performance and cost)* |
| `SECRET_KEY` | Generate with: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GOOGLE_CLIENT_ID` | From Step 1 |
| `GOOGLE_CLIENT_SECRET` | From Step 1 |
| `FRONTEND_URL` | `https://your-app.vercel.app` *(update after Vercel deploy)* |
| `BACKEND_URL` | `https://your-app.railway.app` *(Railway gives you this URL)* |
| `STORAGE_ENDPOINT` | `https://<account-id>.r2.cloudflarestorage.com` |
| `STORAGE_ACCESS_KEY` | From Step 3 |
| `STORAGE_SECRET_KEY` | From Step 3 |
| `STORAGE_BUCKET` | `attachments` |
| `STORAGE_REGION` | `auto` |
| `AI_PROVIDER` | `google` |
| `AI_MODEL` | `gemini-2.5-flash` |
| `GOOGLE_API_KEY` | From Step 2 |
| `OPENAI_API_KEY` | *(optional, only if AI_PROVIDER=openai)* |

### 4.4 Deploy

1. Click **Deploy** (or it deploys automatically on push)
2. Wait for the build to complete — Railway runs `alembic upgrade head` automatically (configured in `railway.json`)
3. Copy the public URL → e.g. `https://d4-ticket-ai.railway.app`

### 4.5 Update Google OAuth redirect URI

1. Back in Google Cloud Console → your OAuth credential
2. Add the production callback URL to **Authorized redirect URIs**:
   ```
   https://d4-ticket-ai.railway.app/api/v1/auth/callback
   ```
3. Save

---

## Step 5 — Vercel (Next.js frontend)

### 5.1 Import project

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import from GitHub → select `D4-ticket-AI`
3. Vercel detects Next.js automatically

### 5.2 Configure settings

- **Framework Preset:** Next.js (auto-detected)
- **Root Directory:** `frontend`
- **Build Command:** `npm run build` (default)
- **Output Directory:** `.next` (default)

### 5.3 Set environment variables

In Vercel → **Environment Variables**, add:

| Variable | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://d4-ticket-ai.railway.app` *(your Railway URL)* |

> `NEXT_PUBLIC_API_URL` must be set at build time because Next.js inlines it into the client bundle. Any change requires a redeploy.

### 5.4 Deploy

Click **Deploy**. Vercel builds and publishes. Your app URL will be something like `https://d4-ticket-ai.vercel.app`.

### 5.5 Update Railway FRONTEND_URL

1. Back in Railway → your backend service → **Variables**
2. Update `FRONTEND_URL` to `https://d4-ticket-ai.vercel.app`
3. Railway redeploys automatically

---

## Step 6 — Verify end-to-end

Open your Vercel URL and run through this checklist:

```
[ ] https://d4-ticket-ai.vercel.app → redirects to /login
[ ] Click "Sign in with Google" → Google OAuth flow completes → redirects to /board
[ ] Create a ticket via "New ticket" button → appears in the list
[ ] Drag a card in Kanban view → status updates in real time
[ ] Open a ticket → add a comment, attach a file (< 10MB)
[ ] Notification bell shows badge when another user comments / assigns
[ ] Click "AI" button in the header → chat panel opens
[ ] Type "show me open tickets" → AI responds with a list
[ ] Type "create a ticket called Test Deployment" → ticket appears in the board
[ ] https://d4-ticket-ai.railway.app/docs → FastAPI Swagger UI works
```

---

## Troubleshooting

### Backend returns 500 on OAuth callback
- Check that the redirect URI in Google Console matches exactly (including trailing slash or lack thereof)
- Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct in Railway

### File uploads fail (500 Storage error)
- Verify `STORAGE_ENDPOINT` format: `https://<account-id>.r2.cloudflarestorage.com` (no trailing slash, no bucket name in URL)
- Confirm the R2 API token has **Object Read & Write** permission on the `attachments` bucket
- Check that `STORAGE_BUCKET=attachments` matches the bucket you created

### AI chat returns "Error"
- Confirm `GOOGLE_API_KEY` is set in Railway and is a valid AI Studio key
- Check Railway logs: `railway logs` — look for LangGraph or API errors
- Switch to OpenAI: set `AI_PROVIDER=openai`, `AI_MODEL=gpt-4o-mini`, add `OPENAI_API_KEY`

### Notifications / WebSocket not connecting
- Browser console: check for `ws://` vs `wss://` — production must use `wss://`
- The frontend derives the WS URL by replacing `http` with `ws` in `NEXT_PUBLIC_API_URL`. Ensure it's `https://` (not `http://`) so it becomes `wss://`

### CORS errors in browser
- `FRONTEND_URL` in Railway must match the exact origin of your Vercel deployment (e.g. `https://d4-ticket-ai.vercel.app` — no trailing slash)
- If you use a custom Vercel domain, update `FRONTEND_URL` to match

---

## Local development (Docker Compose)

```bash
# 1. Clone the repo
git clone https://github.com/ececs/D4-ticket-AI.git
cd D4-ticket-AI

# 2. Create .env from example
cp .env.example .env
# Edit .env — fill in GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_API_KEY

# 3. Start all services
docker compose up --build

# Services:
#   Frontend:  http://localhost:3000
#   Backend:   http://localhost:8000
#   API docs:  http://localhost:8000/docs
#   MinIO UI:  http://localhost:9001  (user: minioadmin / pass: minioadmin)
```

> First run: `docker compose up --build` runs Alembic migrations automatically before starting the server.

---

## Cost summary

| Service | Plan | Cost |
|---|---|---|
| Railway (backend + PostgreSQL) | Starter ($5 credit/month, auto-applied) | $0 |
| Vercel (Next.js frontend) | Hobby | $0 |
| Cloudflare R2 (file storage) | Free (10 GB/month) | $0 |
| Google AI Studio (Gemini 2.5 Flash) | Free (500 req/day) | $0 |
| **Total** | | **$0/month** |
