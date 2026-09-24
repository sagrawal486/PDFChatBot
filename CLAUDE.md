# CLAUDE.md — AI PDF Chatbot

Read this first. It records standing decisions so they don't need repeating.
(Formerly split across this file and `.github/copilot-instructions.md`, now merged here
since the project uses Claude Code going forward.)

## Goal
Portfolio project that should become a real, deployable product (job search and/or revenue),
and a hands-on way to learn AWS. Priorities: working end-to-end product > polish > extras.
Ship in small vertical steps.

## Learning notes for interviews/resume
The user needs to be able to *explain* this project (design decisions, trade-offs, what
each setting does, why), not just have it run. `docs/DESIGN_DECISIONS.md` is that record:
tech stack choices and why, chunking strategy and why, every cost-control setting
(MAX_CHUNKS_PER_DOCUMENT, EMBEDDING_CONCURRENCY, CHAT_MAX_TOKENS, MAX_QUESTIONS_PER_DAY, ...)
explained, known gaps stated honestly, links to primary sources, and a debug-mode
walkthrough (uses the existing `.vscode/launch.json`) for tracing a real request through
every layer. **Update this file whenever a design decision changes or a new one is made**
— don't let it go stale, and proactively add an entry when introducing a new non-obvious
setting or trade-off, even if the user doesn't ask.

## Working agreement
- The user runs any command that needs their machine, credentials, AWS, Docker or a browser.
  Give exact copy-paste commands (PowerShell on Windows unless stated), say what output to
  share back, and continue from that output. Don't ask the user to re-explain context.
- Do code edits, tests and file changes yourself; only hand off what you cannot run
  (anything needing Docker, AWS, or a browser).
- Decide sensible defaults instead of asking; ask only for genuinely user-owned decisions.
- Commit only when asked. Never commit `.env`, `uploads/`, or secrets.
- Never create AWS resources or run billable commands yourself — only the user does that.
- Explain non-trivial architectural changes and trade-offs before or alongside implementing.
- Make the smallest change that preserves the architecture; don't rewrite working code for
  stylistic reasons, don't add dependencies without a reason, don't upgrade pinned versions
  unless asked, don't disable tests/linters to force a pass, never touch unrelated files.

## Cost rule: AWS is the target, spend stays minimal
- The user WANTS to learn AWS, so the real deployment path uses AWS (Bedrock, S3, EC2). Ollama
  is not required and not installed; user has 16GB RAM if a local model is ever wanted instead.
- Keep every external dependency behind a provider interface chosen by env var
  (`CHAT_PROVIDER`, `STORAGE_BACKEND`, embeddings): free/local defaults for dev and tests
  (`simple`, `local`), AWS opt-in (`bedrock`, `s3`). Tests must never call AWS, the internet,
  or paid services — always use injected fakes.
- Bedrock: cheapest suitable model (default `amazon.nova-micro-v1:0`, configurable via
  `CHAT_MODEL_ID`; some regions need an inference-profile id instead of a bare model id),
  capped output tokens (`CHAT_MAX_TOKENS`), bounded context, and per-user daily limits.
  Titan embeddings are cheap.
- Changing embedding model changes vector dimension: `PGVECTOR_DIMENSION` must match, plus a
  migration/re-embed.
- Set an AWS Budget alarm (e.g. $5) before enabling any paid service.

### Low-cost AWS deployment target (learning deployment, not HA)
- One EC2 instance running Postgres+pgvector, Redis, the API and the worker via Docker Compose
  — minimize the number of paid managed services.
- Do NOT use RDS, ElastiCache, NAT gateways, load balancers, CloudFront, or multi-region setup
  for this MVP unless explicitly requested later.
- S3 for PDF storage: one dedicated private bucket, Block Public Access on, a lifecycle rule to
  expire temp objects, least-privilege IAM. Use boto3's default credential chain; use an IAM
  role on EC2, never hardcoded access keys.
- Bedrock for embeddings and chat in the AWS path.
- Stop/terminate the EC2 instance when not in use; periodically check S3, EBS, public IPv4 and
  data-transfer costs.

## Stack decisions
- Backend: FastAPI, SQLAlchemy 2, Alembic, Celery + Redis, PostgreSQL + pgvector, pypdf.
- Frontend: Next.js (App Router, TypeScript) in `frontend/`. Chosen over plain React for
  routing, server rendering, easy Vercel deploy, and better portfolio signal.
- Docker Compose must run the whole stack (db must use `pgvector/pgvector:pg16`).

## Architecture
Dependency flow: `API/Router -> Service -> Repository -> Database`
- Routers: HTTP endpoints, request/response handling, dependency wiring only.
- Services: business rules and use cases.
- Repositories: database access and persistence queries.
- Adapters (storage, embeddings, chat providers, dispatcher): external systems, behind a
  Protocol so fakes can be injected in tests.
- No business logic in routers; no DB access in services or routers; no AWS/Celery/PDF-library
  details leaking into domain logic.

## Coding standards
- Type hints on functions, params, returns, and important attributes.
- Prefer async endpoints for I/O-bound work; use `fastapi.Depends` for DI.
- Pydantic schemas for API contracts and validation.
- Small, focused functions; concise docstrings on public functions/classes/non-obvious test
  helpers.
- Depend on protocols/small interfaces at boundaries (storage, repositories, queues, embedding
  providers, chat providers), injected via constructors or FastAPI dependencies.
- Preserve existing public APIs/contracts unless a change is required and called out.

## Security and configuration
- Never hardcode secrets, tokens, passwords, API keys, or credentials; read from env/settings.
- Never commit `.env` or credentials.
- Never expose password hashes in responses, logs, or errors.
- Validate and authorize access to user-owned resources (documents, chunks, etc.) at the
  service layer — every query for a user-owned row must filter by owner.
- Treat uploaded files and extracted PDF content as untrusted input.
- Bound external calls (timeouts, retries) and keep them observable.

## Roadmap (update as steps complete)
1. Backend: DONE = Bedrock chat provider, pgvector SQL search + migration, documents CRUD,
   CORS, requirements.txt UTF-8, page-aware chunking/citations (page_number column +
   migration, /questions returns QuestionResponse{answer, citations[{document_id,
   chunk_index, page_number, score, excerpt}]}), concurrent embedding batching
   (BedrockEmbeddingProvider.embed_batch, EMBEDDING_CONCURRENCY), per-document chunk cap
   (MAX_CHUNKS_PER_DOCUMENT), per-user daily question limit (question_logs table +
   DailyQuestionLimiter, 429 when MAX_QUESTIONS_PER_DAY exceeded).
   TODO = streaming answers, conversation history.
2. DONE = Docker Compose full stack (docker/Dockerfile, docker/docker-compose.yml: postgres,
   redis, api, worker; api runs `alembic upgrade head` on start; defaults to
   CHAT_PROVIDER=simple / STORAGE_BACKEND=local so it needs no AWS) -- verified working
   end-to-end by user, including real Bedrock chat via apac.amazon.nova-micro-v1:0.
   DONE = GitHub Actions CI (.github/workflows/ci.yml: pytest + compileall + docker build,
   triggers on every branch push and PR). NOT YET pushed to GitHub -- badge markdown:
   `![CI](https://github.com/sagrawal486/PDFChatBot/actions/workflows/ci.yml/badge.svg)`
   (add to README once pushed).
3. Next.js frontend (frontend/, App Router 16, TypeScript, Tailwind v4, React 19; scaffolded
   with `create-next-app --empty`, no extra UI libs). DONE = auth (register/login/logout via
   AuthProvider context, JWT in localStorage, client-side AuthGuard redirect), documents page
   (upload, list, delete, status polling every 3s while uploaded/processing), chat page
   (ask + citations shown per answer, 429 daily-limit handled). Verified: `npm run lint` and
   `npm run build` clean, auth contract (JSON register / form-encoded login) checked against
   the live backend. `frontend/.env.local` -> NEXT_PUBLIC_API_URL=http://localhost:8000.
   TODO = streaming answers, conversation history persistence, PDF viewer with cited-page
   jump, upload progress bar. NOT YET run in a real browser by the user -- do that next.
4. Deploy: single EC2 + Docker Compose (see low-cost target above), S3 storage, Bedrock;
   README with diagram/GIF; then pick a niche and add billing.

## Conventions
- Add/adjust tests with every change; run `pytest` before reporting done. Never claim tests
  passed without fresh output (yours from running them, or the user's from a command you gave).
- Migrations via Alembic for every schema change; review autogenerated migrations before
  applying.
- Keep normal tests independent of AWS credentials, the internet, and paid services. Any
  real-AWS smoke test must be explicit, opt-in, isolated to a dev bucket/resource, and clearly
  labeled as potentially billable.

### Reference commands (repo root)
```powershell
docker compose -f docker/docker-compose.yml up -d            # postgres+redis only (local dev)
docker compose -f docker/docker-compose.yml up --build        # full stack: +api +worker
alembic upgrade head
alembic revision --autogenerate -m "describe change"
uvicorn app.main:app --reload
celery -A app.worker.celery_app worker --loglevel=info --pool=solo
pytest -q
python -m compileall -q app tests
```
