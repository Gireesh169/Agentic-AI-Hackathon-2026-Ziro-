# Free Learning Path Builder — Hackathon MVP

A React/Vite frontend + FastAPI agent backend for building evidence-backed weekly learning plans.

## Features

- OpenAI-powered structured learning plan generation, with a deterministic fallback when `OPENAI_API_KEY` is not configured.
- Time-budget validation enforced by backend code.
- Curated public learning-resource catalog and live URL verification.
- Conservative `FREE` / `PAID` / `UNKNOWN` classification with evidence.
- Approval-gated mock scheduling; no real calendar events are created by this starter.
- Idempotent scheduling: repeated approvals add only missing sessions.
- TC1–TC4 scenario runner and pytest tests.
- Optional Supabase persistence; works locally in memory if Supabase variables are omitted.
- Supabase Google authentication with saved, user-owned roadmaps when configured.

## 1. Requirements

- Python 3.10+
- Node.js 20+ recommended
- VS Code
- OpenAI API key (optional for initial smoke test; required for AI-generated plans)
- Supabase project (optional for initial smoke test; required for persistent cloud storage)

## 2. Start the backend

Open a terminal in VS Code:

```bash
cd backend
python -m venv .venv
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install packages:

```bash
pip install -r requirements.txt
cp .env.example .env
```

On Windows, copy `.env.example` to `.env` manually if `cp` is unavailable.

Edit `backend/.env`. Add your OpenAI key and Supabase values if available. Never commit `.env`.

The example file contains placeholders only. If a real credential has ever been
placed in an example file, source file, Git history, log, screenshot, or shared
archive, revoke it and issue a replacement before using or publishing the
project. Do not paste credentials into frontend files or variables beginning
with `VITE_`; Vite exposes those variables to browser code and the production
bundle.

The repository ignores `.env` files, virtual environments, frontend
dependencies, build output, secret directories, and common private-key file
extensions. Keep local credentials in an untracked `backend/.env`, a deployment
secret manager, or CI secret storage.

Run:

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs to inspect the API. Health check: http://localhost:8000/health

## 3. Set up Supabase

1. Create a project at https://supabase.com.
2. Open SQL Editor.
3. Run `supabase/schema.sql`.
4. In Project Settings / API Keys, copy the project URL and a server-side secret key into `backend/.env`.
5. Keep `SUPABASE_SECRET_KEY` on the backend only. Do not put it in Vite environment variables.

The server-side secret key bypasses RLS. It is used only by FastAPI; never expose it to the browser. Authenticated roadmap routes still enforce the verified Supabase user ID in the backend before every read or write.

The legacy `learning_plans` tables remain for compatibility and are not the
source of truth for authenticated saved roadmaps. New roadmap data uses the
owner-scoped `roadmaps`, `roadmap_weeks`, and `roadmap_resources` tables with
RLS policies. Never trust a user ID supplied directly by the frontend.

If a credential may have been exposed:

1. Revoke or rotate it in the provider console.
2. Replace the local value in `backend/.env` or the deployment secret store.
3. Search tracked files and history without printing secret values.
4. Check provider audit logs and billing for unexpected use.
5. Re-run the configuration-safety tests before publishing.

## 3a. Configure Google authentication and saved roadmaps

The authenticated roadmap flow requires a Supabase project. Run the additive
tables and policies in `supabase/schema.sql`; do not drop the legacy tables.

In Supabase Dashboard:

1. Enable **Authentication → Providers → Google**.
2. Configure the Google OAuth client ID and client secret in Supabase only.
3. In Google Cloud, keep `http://localhost:5173` under **Authorized
   JavaScript origins** and add the Supabase callback URL
   `https://your-project.supabase.co/auth/v1/callback` under **Authorized
   redirect URIs**. In Supabase **Authentication → URL Configuration**, set
   `http://localhost:5173` as the Site URL and add it to the allowed redirect
   URLs. Add the deployed frontend origin and its Supabase callback before
   production use.
4. Keep the Supabase secret/service-role key only in `backend/.env`.
5. Put the project URL and publishable/anon key in `frontend/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=replace-with-your-supabase-anon-key
VITE_API_BASE_URL=http://localhost:8000
```

The frontend uses Supabase's `signInWithOAuth({ provider: "google" })` flow.
The backend validates the resulting bearer token with Supabase Auth and uses
the verified subject for every roadmap operation. A client-supplied `user_id`
is never accepted as proof of ownership.

Google OAuth cannot be verified until the Supabase provider, Google client,
redirect URLs, and real credentials are configured. Without those settings,
the app displays a configuration/authentication error rather than a fake login.

## 4. Start the frontend

Open a second VS Code terminal at the project root:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open the URL printed by Vite (normally http://localhost:5173).

Set `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` if needed.

## 5. Run tests

From the project root, with the backend virtual environment activated:

```bash
cd backend
pytest -q
```

Run official demo scenarios from the website's Test Lab or with:

```bash
cd /Users/apple/Downloads/free-learning-path-builder/backend
source .venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000

curl -X POST http://localhost:8000/api/test-cases/run-all
```

## 6. API routes

- `GET /health`
- `POST /api/plan`
- `GET /api/me`
- `GET /api/roadmaps`
- `GET /api/roadmaps/{roadmap_id}`
- `PATCH /api/roadmaps/{roadmap_id}`
- `POST /api/roadmaps/{roadmap_id}/duplicate`
- `DELETE /api/roadmaps/{roadmap_id}`
- `PATCH /api/roadmaps/{roadmap_id}/weeks/{week_id}`
- `PATCH /api/roadmaps/{roadmap_id}/resources/{resource_id}`
- `POST /api/resources/verify`
- `POST /api/approvals/preview`
- `POST /api/approvals/{plan_id}`
- `GET /api/plans/{plan_id}`
- `POST /api/test-cases/run-all`

## 7. Two-day build priorities

Day 1: run locally, add API keys, test planning, inspect source evidence.
Day 2: finish TC1–TC4, deploy backend and frontend, capture evidence screenshots, prepare slides.

## Important limits

- Resource discovery uses a small curated catalog; it is not a general web search crawler.
- Pricing detection is heuristic. `UNKNOWN` means human review is required.
- Scheduling is deliberately mocked. It demonstrates approval and idempotency without creating real calendar events.
- Enrollment is not automated in this starter.
- Do not claim test scenarios passed until you run them and save the actual results.
