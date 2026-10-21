# PathPilot

PathPilot is a learning-roadmap builder. A user enters a career goal, current
skill level, available study time, and target duration. The app creates a
weekly learning plan with activities and public learning resources.

The project has:

- A React and Vite frontend.
- A FastAPI backend.
- OpenAI roadmap generation with a safe fallback plan.
- Supabase Authentication and database storage.
- Google sign-in through Supabase Auth.
- Saved roadmaps, progress tracking, resource checks, and approval previews.

This is a hackathon MVP. Scheduling is a mock workflow. It does not create real
calendar events or enroll users in courses.

## How the project works

The main flow is:

1. The user signs in with Google.
2. The user enters a goal, skill level, weekly hours, and duration.
3. The backend creates and validates a roadmap preview.
4. The user reviews the weeks, activities, and resources.
5. The user clicks **Add to Saved Roadmaps**.
6. The backend saves the roadmap, weeks, and resources for that user.
7. The user can open the roadmap later from **Saved Roadmaps**.

The backend verifies the Supabase access token. It never trusts a user ID sent
by the browser.

## Project structure

```text
free-learning-path-builder/
├── backend/
│   ├── app/
│   │   ├── agent.py          # OpenAI generation and fallback plans
│   │   ├── auth.py           # Supabase token verification
│   │   ├── main.py           # FastAPI routes
│   │   ├── models.py         # Request and response validation
│   │   ├── resources.py      # Resource catalog and URL checks
│   │   ├── store.py          # Memory and Supabase persistence
│   │   └── test_cases.py     # TC1–TC4 demo scenarios
│   ├── tests/
│   │   ├── test_agent.py
│   │   ├── test_roadmaps.py
│   │   └── test_security_config.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Main application UI
│   │   ├── main.jsx          # React entry point
│   │   └── styles.css        # Application styles
│   ├── .env.example
│   ├── package.json
│   └── vite.config.js
├── supabase/
│   └── schema.sql            # Database tables, indexes, and RLS policies
└── README.md
```

## Requirements

Install these tools before starting:

- Python 3.10 or newer.
- Node.js 20 or newer.
- npm.
- A Supabase project for Google login and saved roadmaps.
- An OpenAI API key for AI-generated plans. The app can use a fallback plan
  when OpenAI is unavailable.

## Run the backend

Open a terminal in the project root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

Edit `backend/.env` with your local values:

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o-mini

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-server-side-key

FRONTEND_ORIGINS=http://localhost:5173
```

The backend accepts `SUPABASE_SECRET_KEY` as an alternative server-side
variable, but if both variables are present it uses
`SUPABASE_SERVICE_ROLE_KEY`.

For a deployed frontend, set the Render environment variable to the exact
Vercel URL. Multiple origins can be separated with commas:

```env
FRONTEND_ORIGINS=http://localhost:5173,https://your-project.vercel.app
```

Do not add a trailing slash to either origin. Redeploy or restart Render after
changing this value.

Start FastAPI from the `backend` directory:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Useful backend URLs:

- API documentation: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

The health response shows whether Supabase and OpenAI are configured. It never
returns the actual keys.

## Run the frontend

Open a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
```

Edit `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-or-publishable-key
```

Start Vite:

```bash
npm run dev
```

Open the URL shown by Vite, usually <http://localhost:5173>.

Only the Supabase URL and anon/publishable key belong in the frontend. Never
put an OpenAI key, service-role key, or Supabase server secret in a variable
starting with `VITE_`. Vite includes `VITE_` variables in the browser bundle.

## Configure Supabase

### Database

1. Open the Supabase project dashboard.
2. Open **SQL Editor**.
3. Run [`supabase/schema.sql`](./supabase/schema.sql).

The schema adds these authenticated tables:

- `profiles`
- `roadmaps`
- `roadmap_weeks`
- `roadmap_resources`

Weeks belong to a roadmap, and resources belong to a week. Foreign keys use
cascade deletion. RLS policies limit access to the authenticated roadmap owner.
The older legacy tables are kept for compatibility.

Do not drop tables or disable RLS.

### Google login

1. In Supabase, open **Authentication → Providers → Google**.
2. Enable Google.
3. Add the Google OAuth client ID and client secret.
4. In Google Cloud, add this JavaScript origin:

   ```text
   http://localhost:5173
   ```

5. In Google Cloud, add this authorized redirect URI:

   ```text
   https://your-project.supabase.co/auth/v1/callback
   ```

6. In Supabase, open **Authentication → URL Configuration**.
7. Set the local Site URL to:

   ```text
   http://localhost:5173
   ```

8. Add `http://localhost:5173` to the allowed redirect URLs.

Replace the project URL with your real Supabase project URL. Add your deployed
frontend URL before using the application in production.

Google login cannot be tested from code alone. It must be tested manually after
the provider, OAuth client, and redirect URLs are configured.

## Main application features

### Roadmap generation

`POST /api/plan` validates the user's goal and creates a roadmap preview. It
does not save the roadmap automatically.

The response includes:

- Weekly topics.
- Activities and measurable outcomes.
- Estimated hours.
- Resource suggestions.
- Generation mode: `ai` or `fallback`.
- Model name when AI generation is used.
- Planning warnings.
- Total estimated hours and available hours.

If OpenAI is unavailable, the backend uses a clearly labelled deterministic
fallback plan. It does not pretend that the fallback came from OpenAI.

### Saving roadmaps

`POST /api/roadmaps` saves the current validated preview. It stores the
roadmap, every week, and every resource through the backend.

The preview ID is reused for retries. This prevents repeated clicks from
creating duplicate roadmaps.

After saving, the frontend shows **Saved Successfully** and adds the roadmap
to the Saved Roadmaps page.

### Saved roadmaps and progress

The application supports:

- Listing the current user's roadmaps.
- Opening a saved roadmap.
- Duplicating a roadmap.
- Archiving and restoring a roadmap.
- Deleting a roadmap after confirmation.
- Marking weeks as in progress or completed.
- Marking resources as completed.
- Showing roadmap progress.

All roadmap operations require an authenticated Supabase bearer token.

### Resource verification

The project includes a small curated catalog of public resources. It is not a
general web search engine.

Resource checks report:

- Whether a URL is reachable.
- Whether pricing looks free, paid, or unknown.
- Evidence and check time when available.

An `UNKNOWN` result means the user should review the resource manually. A
successful HTTP response does not prove that a resource is free.

### Approval preview

The Approval page creates a preview of possible study sessions. The user must
approve the preview before mock sessions are created.

The scheduler is intentionally mocked. No real Google Calendar events or course
enrollments are created.

## API routes

### Public or health routes

```text
GET  /health
GET  /api/resources
POST /api/resources/verify
POST /api/test-cases/run-all
```

### Authenticated roadmap routes

```text
POST   /api/plan
POST   /api/roadmaps
GET    /api/me
GET    /api/roadmaps
GET    /api/roadmaps/{roadmap_id}
PATCH  /api/roadmaps/{roadmap_id}
POST   /api/roadmaps/{roadmap_id}/duplicate
DELETE /api/roadmaps/{roadmap_id}
PATCH  /api/roadmaps/{roadmap_id}/weeks/{week_id}
PATCH  /api/roadmaps/{roadmap_id}/resources/{resource_id}
GET    /api/plans/{plan_id}
POST   /api/approvals/preview
POST   /api/approvals/{plan_id}
```

Protected routes return `401` when the bearer token is missing or invalid.

## Run tests and build the frontend

Run the backend tests:

```bash
cd backend
source .venv/bin/activate
pytest -q
```

Build the frontend:

```bash
cd frontend
npm run build
```

Run the four demo scenarios from the backend:

```bash
cd backend
source .venv/bin/activate
curl -X POST http://localhost:8000/api/test-cases/run-all
```

The scenarios cover:

- Time feasibility.
- A resource becoming paid.
- A broken resource.
- Idempotent scheduling.

The resource simulations use controlled fixtures. They are not proof that
every external website is currently available or free.

## Security notes

- Keep `backend/.env` and `frontend/.env` untracked.
- Never commit API keys, OAuth client secrets, access tokens, or service keys.
- Keep Supabase server credentials in the backend only.
- Use the frontend anon/publishable key only in frontend environment variables.
- Do not trust a browser-supplied user ID.
- Keep Supabase RLS enabled.
- Rotate any credential that has appeared in a repository, log, screenshot,
  terminal recording, or shared message.
- After rotating a credential, update the local `.env` and restart the service.

The repository's example environment files contain placeholders. They are safe
templates and must not be replaced with real credentials.

## Known limitations

- The resource catalog is curated and small.
- Pricing detection is heuristic and may return `UNKNOWN`.
- OpenAI rate limits or quota errors use the fallback generator.
- The mock scheduler does not connect to a real calendar.
- Course enrollment is not implemented.
- Google OAuth and live Supabase persistence require dashboard configuration and
  a manual end-to-end test.

## Troubleshooting

### `ModuleNotFoundError: No module named 'app'`

Start Uvicorn from the `backend` directory:

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### `503 Authentication is not configured`

Check that `backend/.env` contains `SUPABASE_URL` and a server-side Supabase
key. Restart FastAPI after changing the file.

### Google says `redirect_uri_mismatch`

Use the Supabase callback URL in Google Cloud:

```text
https://your-project.supabase.co/auth/v1/callback
```

Use `http://localhost:5173` only as the JavaScript origin and Supabase Site URL.

### Roadmap generation returns a rate-limit warning

OpenAI may be out of quota or temporarily rate-limited. The app should use the
fallback roadmap. If saving fails as well, check the Supabase server key and
confirm that the database schema has been run.

## License

This project is a hackathon MVP. Add a project-specific license before
redistributing it.
