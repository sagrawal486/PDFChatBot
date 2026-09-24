# Design decisions and interview notes

This file exists so you (the author) can explain *why* this project looks the way it
does — in an interview, on a resume call, or six months from now. Every "why" below
is the actual reasoning used while building it, not a generic textbook answer. Update
it whenever a decision changes; a stale doc is worse than no doc.

References are linked inline. Where I say "read this," it's worth actually reading —
this doc explains the decision, the link explains the mechanism.

---

## 1. The problem and the shape of the solution

A user uploads a PDF, waits a bit, then asks questions about it and gets answers
grounded in that document, with page citations. That's RAG (Retrieval-Augmented
Generation): instead of an LLM answering from memory (and possibly hallucinating),
you retrieve relevant text first and force the model to answer only from that text.

Background reading: [Pinecone's RAG explainer](https://www.pinecone.io/learn/retrieval-augmented-generation/),
[AWS's own RAG overview](https://aws.amazon.com/what-is/retrieval-augmented-generation/)
(useful since this project deploys on AWS).

### Why background processing instead of doing it all in the request?

Extracting text from a PDF, chunking it, and generating an embedding per chunk can
take seconds to minutes for a large document. Blocking an HTTP request for that long
is bad for the user (the connection may time out) and bad for the server (one worker
thread tied up per upload). So: `POST /documents` does the fast part (validate,
store the file, write a DB row) and hands the slow part to Celery. The client polls
`GET /documents/{id}` for status (`uploaded → processing → ready`/`failed`).

Reading: [Celery's own case for background tasks](https://docs.celeryq.dev/en/stable/getting-started/introduction.html#what-do-i-need),
[FastAPI docs on background tasks vs. real task queues](https://fastapi.tiangolo.com/tutorial/background-tasks/)
(FastAPI's built-in `BackgroundTasks` runs in-process — fine for emails, wrong for
this, because it dies if the API process restarts and doesn't scale across machines).

---

## 2. Layering: Router → Service → Repository → DB

```
API/Router      HTTP concerns only: parse request, call a service, shape the response.
     |
Service         Business rules: "a document must be a PDF under N MB", "a user can
     |          only see their own documents", "citations point at real chunks".
     |
Repository      SQL only. No business rules. Just "get me these rows."
     |
Database        PostgreSQL + pgvector.
```

Adapters (storage, embeddings, chat providers, the Celery dispatcher) sit beside this
stack, each behind a small `Protocol` (structural interface). A service depends on
the *protocol*, not the concrete class, and gets a real implementation via FastAPI's
`Depends()` at request time. See [app/services/retrieval.py](../app/services/retrieval.py)
(`ChunkRepository` Protocol) or [app/services/chat_provider.py](../app/services/chat_provider.py)
(`SimpleChatProvider` vs `BedrockChatProvider`) as concrete examples.

**Why this matters for an interview**: this is dependency inversion (the "D" in
SOLID) applied pragmatically, not as an architecture-astronaut exercise. The payoff
is concrete and testable: every test in `tests/` passes a fake object satisfying the
protocol — no test hits a real database, S3, or Bedrock. That's why `pytest` runs in
under 3 seconds with 87 tests, and why nobody needs AWS credentials to run the suite.

Reading: [Python `typing.Protocol` docs](https://docs.python.org/3/library/typing.html#typing.Protocol),
[FastAPI's dependency injection guide](https://fastapi.tiangolo.com/tutorial/dependencies/),
["A Philosophy of Software Design"](https://web.stanford.edu/~ouster/cgi-bin/book.php)
by John Ousterhout is the best general book on *why* to draw module boundaries where
you do (better than most "clean architecture" blog posts).

---

## 3. Chunking strategy — what it is and why

Code: [app/services/pdf_processing.py](../app/services/pdf_processing.py).

**What happens**: `PdfTextExtractor` pulls text per page (pypdf). `TextChunker`
splits each page's text into fixed-size, overlapping character windows
(`chunk_size=1000`, `overlap=100` by default) — a sliding window, not
sentence/paragraph boundaries. Each resulting chunk keeps the page number it came
from (`PageChunk(page_number, content)`), which is what makes "page 12" citations
possible later.

**Why fixed-size character chunking instead of something smarter (sentence-aware,
semantic, or LLM-based chunking)?**
- It's deterministic, fast, and needs no extra model call — free and instant.
- It's "good enough" for a general-purpose PDF chatbot; smarter chunking (e.g.
  splitting on sentence boundaries with a tokenizer, or semantic chunking that groups
  by topic via embeddings) measurably helps retrieval quality but adds latency, cost,
  and a whole evaluation problem ("smarter" needs to be proven, not assumed).
- The honest trade-off: fixed windows sometimes cut a sentence in half at a chunk
  boundary, which can lose a little context. **The overlap (100 chars) exists
  specifically to mitigate that** — content near a boundary appears in both the
  chunk before and after it, so a fact split across the cut usually still appears
  whole in at least one chunk.

**Why chunk per page instead of chunking the whole document as one string (the
original version of this code did that)?** Citations. If you flatten all pages into
one blob before chunking, you permanently lose which page any given chunk came from.
Chunking per page costs nothing and buys real citations ("this claim is on page 12"),
which is the single biggest trust signal a RAG answer can give a user.

**What would "production-grade" chunking look like, if you wanted to go further?**
Recursive/semantic chunking (e.g. LangChain's
[`RecursiveCharacterTextSplitter`](https://python.langchain.com/docs/how_to/recursive_text_splitter/)
which tries paragraph → sentence → word boundaries before falling back to a hard
cut), or embedding-based semantic chunking. Good talking point for "what would you
improve" in an interview — you understand the trade-off, you made the cheap/fast
choice deliberately, and you know the next step.

Reading: [Pinecone's chunking strategies guide](https://www.pinecone.io/learn/chunking-strategies/)
is the best single overview of the trade-offs between chunking approaches.

---

## 4. Embeddings and vector search

Code: [app/services/embeddings.py](../app/services/embeddings.py),
[app/repositories/document_repository.py](../app/repositories/document_repository.py).

- **Model**: Amazon Titan Text Embeddings V2 (`amazon.titan-embed-text-v2:0`) via
  Bedrock, dimension 1024 (`PGVECTOR_DIMENSION`). Chosen because it's already the
  natural choice on AWS (this project's stated deployment target), cheap per call,
  and needs no separate account/API key beyond AWS.
- **Storage/search**: PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector)
  extension, not a dedicated vector database (Pinecone, Weaviate, Qdrant, etc.).
  **Why**: this app already needs a relational database for users/documents/chunks;
  running a second specialized database adds an operational cost (another service to
  run, another failure mode, another bill) that isn't justified at this scale.
  pgvector gives you approximate nearest-neighbor search *and* normal SQL joins
  (e.g. "only chunks belonging to documents owned by this user") in one query — see
  `search_similar_chunks` in the repository, which joins `document_chunks` to
  `documents` and filters by `user_id` in the same statement. A dedicated vector DB
  earns its cost at a scale (tens of millions of vectors, need for horizontal
  sharding) this project isn't at.
- **Index**: HNSW (`CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)`,
  see the migration in `migrations/versions/e9f0a1b2c3d4_*.py`). HNSW trades a small
  amount of recall for much faster approximate search than a brute-force scan, and
  is pgvector's recommended default for cosine similarity at this data size.
  Reading: [pgvector README](https://github.com/pgvector/pgvector#hnsw),
  [Bedrock Titan Embeddings docs](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-embedding-models.html).
- **Distance metric**: cosine similarity (`1 - cosine_distance`). Cosine ignores
  vector magnitude and compares direction only, which is the standard choice for
  text embeddings (magnitude in these models isn't a meaningful signal).

**How can a question match a chunk with completely different wording?** This
confused me enough while building it to write down clearly. Two separate models do
two separate jobs, and they never touch each other:

```
Question text ──embed()──▶ query_vector (1024 floats)
                                  │
              compare against precomputed chunk_vectors
              via cosine similarity, in Postgres (pgvector)
                                  │
                                  ▼
              top-k matching chunks' TEXT (not vectors)
                                  │
   question TEXT + chunk TEXT ───┴──▶ chat LLM (Nova Micro) ──▶ answer
```

Embeddings are used *only* to find which chunks to retrieve — once found, the chat
model is given plain English (the question and the retrieved chunk text), never a
vector. It works because an embedding model doesn't encode words, it encodes
*meaning*: Titan (like most retrieval-oriented embedding models) is trained on huge
numbers of `(question, relevant passage)` pairs specifically so semantically related
text lands close together in vector space even with zero shared vocabulary — e.g.
"What car does he drive?" and "He owns a red Mustang" can end up close despite
sharing no words, because the model learned that pattern during training. See
[app/services/retrieval.py](../app/services/retrieval.py) (`UserChunkRetriever.search`,
embeds only the question) and [app/services/rag.py](../app/services/rag.py)
(`RagService.answer`, hands retrieved *chunk text* — `citation.content` — to the
chat provider, never an embedding).

**Honest limitation**: dense embedding similarity isn't perfect. If a question's
vocabulary is *truly* unrelated to the document's wording (rare abbreviations, a
different domain's term for the same concept), pure vector search can miss the
right chunk. Production RAG systems often add **hybrid search** — vector similarity
plus traditional keyword/BM25 search, merged or reranked — to catch both kinds of
matches. This project only does pure vector search; naming that trade-off
unprompted, if asked "what would you improve," is a good interview answer.

**Why did retrieval originally load every chunk into Python and rank there, and why
was that changed?** The very first version filtered chunks by user in SQL but
computed cosine similarity in a Python loop — O(all of a user's chunks) per
question, done in the API process. It was fixed to push the `ORDER BY embedding
<=> :query LIMIT k` ranking into Postgres itself, using the HNSW index, so the
database does the heavy lifting and only the top-k rows ever cross into Python. This
is a good "tell me about a time you found and fixed a performance issue" story.

**Concurrent embedding ("batching")**: Titan's `invoke_model` API only accepts one
text per call — there's no true server-side batch endpoint for this model via
`invoke_model` (Bedrock does have async *batch inference* jobs, but those are
S3-file-based and built for huge offline jobs, not a document just uploaded by a
user). So "batching" here means bounded, concurrent calls via a
`ThreadPoolExecutor` (`BedrockEmbeddingProvider.embed_batch`,
`EMBEDDING_CONCURRENCY` env var, default 5) — faster wall-clock time for a
multi-page document without changing the per-call cost.

---

## 5. The chat/answer step

Code: [app/services/chat_provider.py](../app/services/chat_provider.py),
[app/services/rag.py](../app/services/rag.py).

`RagService.answer()`: retrieve top-k chunks for the user's question → concatenate
their text up to `max_context_characters` (default 8000, a safety bound so one
question can't build an unbounded prompt) → pass `(question, context)` to a
`ChatProvider` → return the answer plus which chunks were used as citations.

Two chat providers, chosen by `CHAT_PROVIDER`:
- `simple` (default): returns the retrieved context verbatim. No LLM call, $0,
  works with no AWS setup at all. This is what makes `docker compose up` work for
  anyone cloning the repo with zero configuration — a genuine portfolio
  consideration, not just a fallback.
- `bedrock`: calls Amazon Nova Micro (`amazon.nova-micro-v1:0`) via the
  [Bedrock Converse API](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference-api.html)
  with a system prompt instructing it to answer *only* from the supplied context and
  say so when it can't. This is the core anti-hallucination mechanism of RAG: the
  model is not asked "what do you know about X," it's asked "given exactly this
  text, what's the answer" — constrained generation, not open-ended recall.

**Why Nova Micro specifically?** It's Amazon's own cheapest/fastest Bedrock chat
model — appropriate for a portfolio project where the answer quality bar is
"coherent and grounded," not "state of the art reasoning," and cost matters more
than raw capability. Swappable via `CHAT_MODEL_ID` with no code change.

**A real gotcha worth knowing**: calling `converse()` with the bare model ID
(`amazon.nova-micro-v1:0`) failed with `ValidationException: Invocation of model ID
... with on-demand throughput isn't supported. Retry your request with the ID or
ARN of an inference profile that contains this model.` Some newer Bedrock models
(Nova included) can't be invoked on-demand by their plain model ID in most regions
— you have to address them through a **cross-region inference profile** instead,
found with `aws bedrock list-inference-profiles --region <region> --query
"inferenceProfileSummaries[?contains(inferenceProfileId,'nova-micro')]"`. The
profile ID is prefixed by geography — `apac.amazon.nova-micro-v1:0` for
`ap-south-1` (Mumbai), `us.*`/`eu.*` elsewhere. Practically identical usage (still
just a string in `CHAT_MODEL_ID`), but worth knowing *why* before you hit it cold
in an interview or a demo. Reading: [Bedrock cross-region inference profiles](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html).

**`CHAT_MAX_TOKENS` (default 512)**: caps how many tokens the model is allowed to
*generate* in its reply. Two reasons this exists: (1) cost — Bedrock bills per
output token, so an unbounded reply is an unbounded bill; (2) latency — a shorter
capped reply comes back faster, which matters for a synchronous HTTP endpoint with
no streaming yet. 512 tokens (~350-400 words) is generous for a Q&A answer.

**A real, fully-diagnosed bug: "my" made the model refuse to answer.** Asking
"What is my name, email and phone" against a resume returned *"I could not find
your name, email, and phone in the provided document excerpts. However, I can
identify myself as an AI system built by a team of inventors at Amazon"* — even
though the citations proved the right chunk, containing the exact answer, was
retrieved and in context. So this wasn't retrieval failing (confirmed first,
before touching the prompt — always check retrieval before blaming generation).
It was isolated with a small experiment (calling `converse()` directly, bypassing
the app, varying only the question) that any question phrased with **"my"** failed
— *"What is my email?"* → refused; *"What email is listed?"* → answered correctly,
same context, same document. Nova Micro (the smallest/cheapest Nova tier) appears
to have a baked-in guardrail against confirming "personal information" back to a
user, triggered purely by first-person phrasing, regardless of system-prompt
instructions telling it to ignore that. A first attempt at a fix (a one-line
clarification: "'my' refers to the user") **did not work** — worth stating,
because assuming a plausible-sounding fix works without testing it is exactly how
bugs ship. What did work: an explicit, forceful permission statement naming the
concern directly — *"you are explicitly permitted... this is not a privacy
violation, since the person is asking about their own uploaded content."*
Naming the exact objection the model's guardrail is (probably) trained against
overrides it far more reliably than a vague rephrase. See `SYSTEM_PROMPT` in
`app/services/chat_provider.py` and the regression test in
`tests/test_chat_provider.py` that guards this specific wording. **The general
lesson**: small/cheap LLMs carry safety guardrails you didn't write and can't see,
they can misfire on totally benign requests, prompt fixes need to be *tested
against the real model*, not assumed to work from how reasonable they sound, and
a first attempted fix can fail outright — that's normal, not a sign to give up on
prompting as the fix.

---

## 6. Cost and abuse controls — what each one does and why it exists

All portfolio decisions here trade a little flexibility for a **hard ceiling on AWS
spend**, since this runs on the author's own AWS account.

| Setting | Default | What it bounds | Why this exists |
|---|---|---|---|
| `MAX_UPLOAD_SIZE_MB` | 10 | Size of one uploaded PDF | Bounds worst-case memory/storage per upload and, indirectly, how many chunks one document can produce. |
| `MAX_CHUNKS_PER_DOCUMENT` | 500 | Chunks embedded (and stored) per document | A malicious or absurdly large PDF could otherwise generate thousands of Bedrock embedding calls from one upload. Chunks beyond the cap are dropped (with a logged warning), not rejected outright — the document still becomes usable, just over a bounded portion of its text. See `DocumentProcessingService.process`. |
| `EMBEDDING_CONCURRENCY` | 5 | Parallel Bedrock calls per document | Speeds up processing without opening unbounded concurrent connections to Bedrock (which has its own per-account rate limits you'd otherwise hit and get throttled/retried against). |
| `CHAT_MAX_TOKENS` | 512 | Output tokens per answer | Bounds cost and latency per question (see §5). |
| `MAX_QUESTIONS_PER_DAY` | 30 | Questions answered per user per rolling 24h | The one control that isn't about a single request being too big — it's about *volume*. Without it, one user (or one leaked demo link) could run unbounded Bedrock chat+embedding calls. Enforced in `POST /questions` via `DailyQuestionLimiter`, checked *before* calling Bedrock, so a blocked request costs nothing. See `app/services/usage_limiter.py`. |

**Why a rolling 24-hour window instead of a calendar day?** Simpler to reason about
and implement (`count_since(user_id, now - 24h)`), and avoids a burst-at-midnight
edge case where a calendar-day counter resets and a user immediately gets a fresh
30 questions.

General reading on why every external/paid call in this codebase is bounded:
[AWS's own cost-control guidance for Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-service.html)
and simply: **an LLM API without server-side limits is an unbounded liability** —
this is a standard, expected concern in any RAG system design interview.

---

## 7. Auth

Code: [app/core/security.py](../app/core/security.py), [app/core/jwt.py](../app/core/jwt.py).

- Passwords hashed with **bcrypt** (via the `bcrypt` package directly, with a random
  salt per password — `bcrypt.gensalt()`). bcrypt is deliberately slow (adjustable
  work factor) which is the point: it makes brute-forcing a stolen hash database
  expensive. Reading: [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html).
- **Stateless JWT access tokens** (`python-jose`, HS256, symmetric secret
  `JWT_SECRET_KEY`), 30-minute expiry by default. Stateless means no server-side
  session store to scale or invalidate — trade-off: you can't revoke a single token
  early without extra machinery (a blocklist, or short expiry + refresh tokens,
  neither of which this project has yet — a known gap, good to name if asked "how
  would you handle a compromised token?").
- Every user-owned resource (documents, chunks, question logs) is filtered by
  `user_id` at the repository query itself (`get_for_user`, `get_chunks_for_user`
  style methods), not just checked in application code after fetching — so there's
  no code path that can accidentally load another user's row. This is the
  "authorization at the data-access boundary" pattern, worth naming explicitly in
  an interview as a deliberate defense against IDOR-style bugs
  ([OWASP: Insecure Direct Object Reference](https://owasp.org/www-community/attacks/Insecure_Direct_Object_Reference)).

---

## 8. Storage abstraction (local vs. S3)

Code: [app/services/storage.py](../app/services/storage.py),
[app/services/s3_storage.py](../app/services/s3_storage.py).

Both implement the same `Storage` protocol (`put`/`get`/`delete`), selected by
`STORAGE_BACKEND`. Local storage needs zero setup (great for `docker compose up`
with no AWS account); S3 is the real deployment target. Because the rest of the app
only depends on the `Storage` protocol, switching backends is a one-line env change,
never a code change — the actual point of the interface, not just "because SOLID
says so."

---

## 9. Docker Compose design

Code: [docker/Dockerfile](../docker/Dockerfile), [docker/docker-compose.yml](../docker/docker-compose.yml).

- One image, two roles: the `api` and `worker` containers are built from the *same*
  Dockerfile/image, just started with different commands (`uvicorn ...` vs
  `celery ... worker`). Avoids maintaining two near-identical Dockerfiles.
- `api`'s command is `alembic upgrade head && uvicorn ...` — migrations run
  automatically on container start, so `docker compose up` alone is a complete,
  working demo. (Trade-off: running migrations from the app container isn't how
  you'd do it at real scale — you'd run migrations as a separate one-shot job/step
  in CI/CD so N replicas of the API don't all race to migrate at once. Fine here
  since there's exactly one `api` replica.)
- `depends_on: condition: service_healthy` (not just `depends_on:`) on postgres and
  redis — a plain `depends_on` only waits for the container to *start*, not for
  Postgres to actually be ready to accept connections, which is a classic source of
  "worked on my machine, flaky in CI" bugs. Health checks (`pg_isready`, `redis-cli
  ping`) close that gap.
- Uploaded files live in a **named volume shared by `api` and `worker`**
  (`uploads_data:/app/uploads` on both) — they're separate containers with separate
  filesystems, so without a shared volume the worker couldn't read a file the API
  container wrote to local disk. (This is exactly the kind of bug that doesn't show
  up until you actually containerize — worth mentioning if asked about debugging.)
- Defaults to `CHAT_PROVIDER=simple`, `STORAGE_BACKEND=local` — the whole stack
  runs with **zero AWS credentials**, which matters a lot for "anyone can clone this
  from my resume and run it."

Reading: [Compose file healthcheck reference](https://docs.docker.com/reference/compose-file/services/#healthcheck),
[`depends_on` with conditions](https://docs.docker.com/compose/how-tos/startup-order/).

---

## 10. Testing approach

Every collaborator crossing a real boundary (DB, S3, Bedrock, Celery) is a
`Protocol`, and every test supplies a hand-written fake, not a mock library and not
a real service. Example: `tests/fakes.py`, or the `FakeBedrockClient` in
`tests/test_embeddings.py`. This means:
- 87 tests run in ~2-3 seconds, no network, no AWS account needed, no flaky CI.
- Tests double as executable documentation of each collaborator's contract (what
  methods it needs, what it returns) — reading a fake tells you the interface
  faster than reading the Protocol definition alone.

Trade-off, stated honestly: hand-written fakes can drift from the real
implementation's behavior if not kept in sync (e.g. a fake `search_similar_chunks`
returning a 5-tuple has to be updated by hand if the repository's real return shape
changes — which happened more than once while building this). There's no
integration test that runs the real Postgres+pgvector query end-to-end; that's a
gap worth naming if asked "what's *not* tested here."

**A real example of that gap biting**: `DocumentRepository` detected whether
pgvector was active by checking
`DocumentChunk.__table__.c.embedding.type.__class__.__name__ == "Vector"`. That
string comparison always evaluated `False`, because pgvector's actual SQLAlchemy
class is named `VECTOR` (`Vector` is just a module-level alias re-exported from
`pgvector.sqlalchemy`) — confirmed by reading pgvector's installed source directly
(`python -c "from pgvector.sqlalchemy import Vector; import inspect;
print(inspect.getsource(Vector))"`). So embeddings were silently written as JSON
strings instead of raw vectors, and pgvector's own bind processor then tried to
`numpy.asarray(that_json_string, dtype='>f4')` — numpy treats a whole string as one
scalar to convert, so it failed with `ValueError: could not convert string to
float: '[-0.045, ...]'` on every document processed. **No test caught this**,
because every test touching serialization used a fake repository — the real
`DocumentRepository` class was never imported or exercised by `pytest` at all. Found
only by running the real worker end-to-end and reading a live traceback.

The fix: stop re-deriving "is pgvector active" from a fragile string compared
against the table's runtime type, and instead compute it once, in one place
(`USES_PGVECTOR` in `app/models/document_chunk.py`, the same boolean that decides
the column's type in the first place) and import that everywhere it's needed. The
lesson generalizes: **derive a fact once, at its source, and reuse it — don't
re-derive the same fact a second way somewhere else**, because the two derivations
can silently disagree. `tests/test_document_repository.py` now imports the real
`DocumentRepository` (no fake) specifically to close this coverage hole.

---

## 11. What's deliberately not built yet (and why that's fine to say out loud)

- **Streaming answers** — the chat call is synchronous request/response, not
  token-by-token streaming (SSE/WebSocket). Straightforward to add later; skipped
  because it doesn't change whether the core RAG pipeline is correct.
- **Conversation history / multi-turn** — each question is independent; there's no
  "what did I just ask" follow-up context yet.
- **Frontend** — API-only so far; Next.js frontend is the next planned step (see
  `CLAUDE.md`).
- **No token-level cost tracking/dashboard** — the daily question count limits
  volume, but there's no per-user token/cost accounting yet.

Naming known gaps precisely, unprompted, is a stronger interview signal than
pretending the project is "finished."

---

## 12. How to actually learn the code by running it (not just reading it)

Reading code top-to-bottom rarely builds real understanding. Better: **set a
breakpoint, send a real request, and watch execution jump through the layers.**

### Run in debug mode (VS Code)

This repo already has `.vscode/launch.json` with two configs — **"Python Debugger:
FastAPI"** and **"Python: Debug Celery Worker"**. Open the Run and Debug panel
(`Ctrl+Shift+D`), pick one from the dropdown, press F5. Run Postgres/Redis first so
both have something to connect to:

```powershell
docker compose -f docker/docker-compose.yml up -d postgres redis
```

(Skip the `api`/`worker` containers here — you want VS Code running the API/worker
itself, in the debugger, not Docker running them.)

Reading: [VS Code Python debugging docs](https://code.visualstudio.com/docs/python/debugging).

### A concrete walkthrough exercise

1. Set a breakpoint in `app/api/auth.py` at `service.register(request)`, start the
   "FastAPI (debug)" config, open http://localhost:8000/docs (FastAPI's auto-generated
   Swagger UI — the fastest way to fire real requests without writing curl), and call
   `POST /auth/register`. Step into `UserService.register` → `hash_password` →
   `UserRepository.create`. You've now traced the full auth write path.
2. `POST /auth/login`, copy the `access_token`, click **Authorize** in `/docs` and
   paste `Bearer <token>`.
3. Breakpoint in `app/services/document_service.py` at `upload()`. Call
   `POST /documents` with a real PDF. Step through the PDF-signature check, the
   `storage.put()` call, and `dispatcher.enqueue()` — notice this returns
   *immediately*; processing hasn't happened yet.
4. Now the interesting part: attach the "Celery worker (debug)" config too (VS Code
   supports multiple simultaneous debug sessions), set a breakpoint in
   `DocumentProcessingService.process`, and watch the Celery task pick up the queued
   document asynchronously — this is where you *see* the async boundary from §1,
   not just read about it. Step through extraction → chunking → (if
   `CHAT_PROVIDER`/embeddings are configured) embedding → `replace_chunks_with_embeddings`.
5. Breakpoint in `app/api/questions.py` at `ask_question`. Call `POST /questions`.
   Step through `limiter.ensure_within_limit` → `RagService.answer` →
   `UserChunkRetriever.search` (watch the SQL `search_similar_chunks` call) →
   `chat_provider.answer`.

After that single walkthrough you'll have traced every layer this doc describes,
with a debugger proving it rather than a diagram claiming it.

### Alternative: no debugger, just watch it happen

`docker compose -f docker/docker-compose.yml logs -f api worker` in one terminal,
`/docs` in a browser in another. Slower to build deep understanding than stepping
through with breakpoints, but zero setup and still shows the async hand-off between
`api` (fast, returns immediately) and `worker` (picks the job up seconds later) in
the log timestamps.
