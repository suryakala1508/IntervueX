# IntervueX

An adaptive AI interview and assessment platform. It reads your resume and the
job you are targeting, generates interview questions grounded in both, grades
every answer against a fixed rubric, adapts the next question to how the last
one went, and finishes with an improvement plan.

```
React (Vite, Tailwind)
        |
        v
FastAPI  --  REST + SSE
        |
        |-- auth / profile / documents / interviews / evaluation
        |-- LangGraph workflow  ->  validated tool surface  ->  audit log
        |
        |-- PostgreSQL + pgvector
        |-- LLM and embedding providers
```

## It runs with no API keys

Every AI capability has a deterministic offline implementation. With no
`ANTHROPIC_API_KEY`, questions, grading, and plans come from a rule-based
provider instead of a model, and the product works end to end. Add the key and
the same interfaces route to Claude. The same applies to embeddings (a local
hashing embedder stands in for Voyage) and to vectors (cosine similarity in
Python stands in for pgvector).

This is what lets the test suite run with no database server, no network, and no
keys - and what makes the `/health` endpoint worth reading:

```json
{ "status": "ok", "llm_provider": "offline", "embedding_provider": "hashing", "vector_backend": "fallback" }
```

## Quick start

### Backend

```bash
cd backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# Zero-infrastructure option: SQLite and the offline providers.
echo 'DATABASE_URL=sqlite:///./intervuex.db' >> .env
echo 'VECTOR_BACKEND=fallback' >> .env

python -m scripts.seed_demo        # optional demo account and history
uvicorn app.main:app --reload
```

API docs at http://localhost:8000/docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173. The dev server proxies `/api` to port 8000, so no CORS
configuration is needed while developing.

Seeded sign-ins (after `seed_demo`): `demo@intervuex.app` / `demo1234`, and
`admin@intervuex.app` / `admin1234` for the administrator view.

### Everything in Docker

```bash
docker compose up --build      # PostgreSQL + pgvector, API, built frontend
```

## Tests

```bash
cd backend  && pytest      # 78 tests, no services required
cd frontend && npm test    # 51 tests
```

The backend suite runs against a throwaway SQLite file and the offline
providers. It covers auth and token handling, ownership isolation between users,
document ingestion and chunking, the adaptive interview loop, SSE streaming,
completion, and dashboard aggregation.

## How the interview works

The workflow is a LangGraph state machine, and the control flow is deliberately
*not* the model's to choose. The model decides the content of questions and the
grading of answers; pure Python decides what happens next.

```
start:   load_context -> plan_questions -> ask_first_question

answer:  load_context -> record_answer -> evaluate -> update_state
                      -> (decide) -> generate_follow_up
                                  -> next_planned_question
                                  -> finalize
```

`decide_next_step` is an ordinary function over the state. A strong answer
raises the difficulty a rank and earns a deeper follow-up; a weak or incomplete
one lowers it and steps back to fundamentals. Follow-ups never chain, and they
are capped at half the planned interview length, so an interview cannot wander.

### The tool surface

The workflow never issues its own SQL. Every read and write goes through
`app/ai/tools.py`, where each function validates its arguments, enforces that
the acting user owns the row being touched, and appends a row to `tool_logs`.
The administrator view renders that audit trail directly.

```
get_candidate_profile()          search_candidate_documents(query)
retrieve_job_requirements()      generate_interview_question(topic, difficulty)
evaluate_answer(answer, rubric)  create_improvement_plan(scores)
save_interview_result(result)
```

### Retrieval

Uploads are extracted, cleaned, chunked with overlap (so a requirement
straddling a boundary stays retrievable from either side), embedded, and stored
with their user, document, page, and chunk index. Question generation retrieves
against the candidate profile and the active job description, and each generated
question records the chunk ids it was grounded in.

## Project layout

```
backend/
  app/
    api/v1/        auth, profile, documents, jobs, interviews, dashboard, admin
    services/      request-level orchestration
    ai/            workflow (LangGraph), tools, providers, prompts, schemas
    models/        SQLAlchemy ORM
    schemas/       Pydantic request and response models
    db/            engine, base, vector backend selection
  tests/           78 tests
  scripts/         seed_demo.py

frontend/
  src/
    pages/         dashboard, profile, jobs, documents, interviews, room, admin
    components/    layout, route guard, UI primitives, chart
    context/       auth
    lib/           API client, async hook
```

## API

```
POST   /api/v1/auth/register           POST   /api/v1/auth/login
POST   /api/v1/auth/refresh            POST   /api/v1/auth/logout
GET    /api/v1/users/me

GET    /api/v1/profile                 PUT    /api/v1/profile
POST   /api/v1/profile/resume

POST   /api/v1/jobs                    GET    /api/v1/jobs
GET    /api/v1/jobs/{id}               POST   /api/v1/jobs/{id}/activate
POST   /api/v1/jobs/upload

POST   /api/v1/documents/upload        GET    /api/v1/documents
DELETE /api/v1/documents/{id}          GET    /api/v1/documents/search?q=

POST   /api/v1/interviews              GET    /api/v1/interviews
GET    /api/v1/interviews/{id}         GET    /api/v1/interviews/{id}/question
POST   /api/v1/interviews/{id}/answer
POST   /api/v1/interviews/{id}/answer/stream    (SSE)
POST   /api/v1/interviews/{id}/complete
POST   /api/v1/interviews/{id}/abandon
GET    /api/v1/interviews/{id}/plan    DELETE /api/v1/interviews/{id}

GET    /api/v1/dashboard
GET    /api/v1/admin/overview          GET    /api/v1/admin/users
GET    /api/v1/admin/tool-logs
```

## Configuration

Full list with defaults in `backend/.env.example`. The ones that matter:

| Variable | Default | Notes |
| --- | --- | --- |
| `DATABASE_URL` | local PostgreSQL | `sqlite:///./intervuex.db` works too |
| `SECRET_KEY` | dev placeholder | **Required** in production - the app refuses to boot without it |
| `ANTHROPIC_API_KEY` | unset | Unset means the offline provider |
| `VOYAGE_API_KEY` | unset | Unset means the local hashing embedder |
| `VECTOR_BACKEND` | `auto` | `auto` probes for pgvector; `fallback` computes in Python |
| `CORS_ORIGINS` | localhost:5173 | Comma-separated; set to your deployed frontend |

## Deployment

**Backend** (Render, Railway, Fly): deploy `backend/Dockerfile`. Set
`DATABASE_URL`, a real `SECRET_KEY`, and `CORS_ORIGINS` to the frontend's
origin. `$PORT` is honoured automatically. Schema creation runs at startup.

**Frontend** (Vercel, Netlify, or the included nginx image): build with
`VITE_API_BASE_URL` set to the API's public origin. Vite inlines `VITE_*` at
build time, so changing it requires a rebuild. For static hosts, route all paths
to `index.html` - the included `nginx.conf` already does.

## Notes on the design

**Portability was a constraint, not an afterthought.** IDs are UUID strings and
structured columns are JSON rather than JSONB, so the same models run unchanged
on PostgreSQL and SQLite. That is what makes the test suite infrastructure-free.

**Auth.** bcrypt with an explicit 72-byte guard (bcrypt silently truncates past
it, which would let two different passwords open one account). Short-lived
access tokens, longer refresh tokens, and token type checked on decode so a
refresh token cannot be used as an access token. Login failures are
indistinguishable between a wrong password and an account that does not exist.

**Ownership.** Every route resolves the row through a helper that checks the
acting user and returns 404 - not 403 - for someone else's data, so the API does
not confirm that an id exists.

**Errors.** AI failures are 502 with the reason, not a 500. The improvement plan
returns 404 until the interview is completed. Answering a completed interview or
a question twice is a 409. The SSE endpoint validates before opening the stream,
so a bad request is still an ordinary status code rather than an error buried
inside a 200.
