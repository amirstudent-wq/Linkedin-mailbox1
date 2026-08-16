# LinkedIn Mailbox Manager — Claude Code Context

## What this is

A full-stack web app that connects to a personal LinkedIn account, surfaces all
message threads in a filterable inbox, lets the user reply in-app, and runs a
daily Claude-powered scan that drafts replies to unanswered messages according
to user-defined "use cases" (reply personas).

**Stack:** Python FastAPI + SQLite (backend) · Next.js 14 + Tailwind (frontend) ·
`linkedin-api` (unofficial LinkedIn client) · Anthropic Claude API · APScheduler

---

## How to run

### Fastest path (local machine, no Docker)

```bash
# 1. Fill in credentials
cp .env.example .env
# edit .env — see required vars below

# 2. Backend
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload

# 3. Frontend (new terminal)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000.  Press **Sync** → conversations appear.

### Docker

```bash
docker compose up --build
```

### Required env vars (in project-root `.env`)

```
LINKEDIN_EMAIL=you@example.com
LINKEDIN_PASSWORD=yourpassword
ANTHROPIC_API_KEY=sk-ant-...
DAILY_SCAN_HOUR=8          # UTC hour for the automatic daily scan
DAILY_SCAN_MINUTE=0
```

The config module searches `backend/.env` then the project root `.env`
automatically — no need to copy the file.

---

## Project layout

```
linkedin-mailbox1/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, lifespan (DB init + scheduler start)
│   │   ├── config.py        # pydantic-settings, reads .env from root or backend/
│   │   ├── database.py      # async SQLAlchemy engine + get_db dependency
│   │   ├── models.py        # ORM: Conversation, Message, UseCase, AIDraft
│   │   ├── schemas.py       # Pydantic I/O schemas (all API shapes live here)
│   │   ├── routers/
│   │   │   ├── auth.py          GET /api/auth/status
│   │   │   ├── messages.py      GET|POST /api/messages[/{id}[/reply]]
│   │   │   ├── ai.py            POST /api/ai/reply/{id}, GET|PATCH /api/ai/drafts
│   │   │   ├── use_cases.py     CRUD /api/use-cases
│   │   │   └── scheduler.py     POST /api/scheduler/run
│   │   └── services/
│   │       ├── linkedin.py      LinkedIn API wrapper (fetch, send)
│   │       ├── ai_agent.py      Claude reply generation
│   │       └── scheduler.py     APScheduler job + daily scan logic
│   └── requirements.txt
└── frontend/
    └── src/
        ├── app/page.tsx         Root layout: icon nav + 3-column layout
        ├── components/
        │   ├── FilterBar.tsx    Search, filter chips, Sync/AI-Scan buttons
        │   ├── ConversationList.tsx
        │   ├── ConversationThread.tsx
        │   ├── ReplyComposer.tsx   Manual reply + AI generate
        │   ├── DraftsSidebar.tsx   Pending AI drafts (send/dismiss)
        │   ├── UseCasesPanel.tsx   Use case CRUD + system-prompt editor
        │   └── StatusBar.tsx    LinkedIn connection indicator
        ├── services/api.ts      All API calls (axios, single file)
        └── types/index.ts       Shared TypeScript types
```

---

## Key API routes

| Method | Path | What it does |
|--------|------|-------------|
| GET | `/api/auth/status` | Is LinkedIn connected? |
| POST | `/api/messages/sync` | Pull fresh conversations from LinkedIn → DB |
| GET | `/api/messages` | List conversations — supports `unread_only`, `awaiting_reply`, `search`, `sort_by`, `sort_dir` |
| GET | `/api/messages/{id}` | Full thread; fetches messages from LinkedIn if not cached |
| POST | `/api/messages/{id}/reply` | Send a reply via LinkedIn |
| POST | `/api/ai/reply/{id}` | Generate AI draft for a conversation |
| GET | `/api/ai/drafts` | List drafts; `?status=pending\|sent\|dismissed` |
| PATCH | `/api/ai/drafts/{id}` | Update draft status |
| GET/POST/PATCH/DELETE | `/api/use-cases` | Manage AI reply personas |
| POST | `/api/scheduler/run` | Trigger the daily scan immediately |

Interactive docs: http://localhost:8000/docs

---

## Data model (4 tables)

```
Conversation          Message
─────────────         ──────────────────
id (URN string) ◄──── conversation_id
participants (JSON)   id (URN string)
last_message_at       sender_id / name
last_message_text     body
is_read               sent_at
last_message_is_mine  is_mine
awaiting_reply
message_count

UseCase               AIDraft
────────              ──────────────────
id                    id
name                  conversation_id ──► Conversation
description           use_case_id ──────► UseCase
system_prompt         draft_text
is_active             reasoning
                      status  (pending|sent|dismissed)
```

`awaiting_reply = True` when the counterpart sent the last message and we have
not replied.  This is the primary flag the daily scanner filters on.

---

## The LinkedIn service layer

`backend/app/services/linkedin.py` wraps `linkedin-api` (unofficial lib).
Key design choices:

- **Lazy init**: the `Linkedin` client is created on first call, not at import
  time. This lets the server start and serve non-LinkedIn routes even when
  credentials are wrong or missing.
- **All public functions wrap `_get_client()` in try/except** so a bad
  credential returns a structured error (False / RuntimeError), never a 500.
- **`_own_profile_id()`** is called to determine which messages are "mine"
  (needed to compute `last_message_is_mine` and `awaiting_reply`).
- Conversations are normalised into plain dicts before hitting the DB; the raw
  LinkedIn response shapes are never stored or exposed to the frontend.

LinkedIn API method mapping:
```python
api.get_conversations()          → list of threads
api.get_conversation(urn_id)     → events (messages) for one thread
api.send_message(body, conversation_urn_id=urn_id)
api.get_user_profile()           → own profile (for "is_mine" detection)
```

LinkedIn URNs look like `urn:li:messagingThread:2-abcdef…`. These are used as
primary keys for the `conversations` table. URL-encode them when using as path
params (`encodeURIComponent` in JS, `urllib.parse.quote` in Python).

---

## AI reply pattern

`backend/app/services/ai_agent.py`:

1. Takes the last ≤10 messages as a conversation history string.
2. Constructs a system prompt from a `UseCase.system_prompt` (or the built-in
   default if none is provided).
3. Calls `claude-sonnet-4-6` asking for JSON `{"draft": "...", "reasoning": "..."}`.
4. Strips markdown code fences if present, parses JSON, returns the dict.

If `system_prompt` is the literal string `"auto"`, `generate_use_case_prompt()`
is called first — it asks Claude Haiku to write the system prompt from the use
case name and description.

---

## Daily scan flow

`POST /api/scheduler/run` or automatic cron at `DAILY_SCAN_HOUR:DAILY_SCAN_MINUTE` UTC:

1. `fetch_conversations(limit=100)` from LinkedIn
2. Upsert into `conversations` table
3. Filter to `awaiting_reply = True`
4. For each: fetch messages → build history
5. For each active `UseCase`: if no `pending` draft exists for (conversation,
   use_case), generate one via Claude and insert into `ai_drafts`
6. Return `{conversations_scanned, unanswered_found, drafts_created, errors[]}`

Drafts appear in the **AI Drafts** sidebar. The user can Send (which calls the
reply endpoint and marks the draft `sent`) or Dismiss (marks it `dismissed`).

---

## Frontend data flow

```
page.tsx
  useQuery(["conversations", filters])   → GET /api/messages?...
  useQuery(["conversation", selectedId]) → GET /api/messages/{id}
  │
  ├─ FilterBar      ← writes filters state up to page.tsx
  ├─ ConversationList ← reads conversations, emits selectedId
  ├─ ConversationThread ← reads activeConversation.messages
  ├─ ReplyComposer  ← POST /api/messages/{id}/reply
  │                    POST /api/ai/reply/{id}
  ├─ DraftsSidebar  ← GET /api/ai/drafts?status=pending
  │                    PATCH /api/ai/drafts/{id}
  └─ UseCasesPanel  ← CRUD /api/use-cases
```

State is minimal: `selectedId` (string|null) and `filters` object live in
`page.tsx`. Everything else is server state managed by React Query.

The Next.js `rewrites()` in `next.config.js` proxy `/api/*` to the backend, so
the frontend never hits the backend URL directly — it always talks to `/api/...`
on its own origin. This means `NEXT_PUBLIC_API_URL` is only needed at build time
for the Docker image; in dev it defaults to `http://localhost:8000`.

---

## Known limitations and extension points

**LinkedIn ToS**: `linkedin-api` uses session-based unofficial access. LinkedIn
may rate-limit or challenge logins from unusual IPs (e.g. cloud servers).
Running on your own machine with your normal IP is most reliable.

**2FA**: If your LinkedIn account has 2FA enabled, the library will prompt
interactively on first run. Run the backend once in a terminal to complete the
2FA flow; the session cookie is cached by the library in `~/.cache/linkedin-api/`.

**Extending filters**: Add query params in `messages.py` → `list_conversations()`
and mirror them in `frontend/src/services/api.ts` → `getConversations()`.

**Webhook / real-time**: The app polls on a 30s interval (`refetchInterval`).
For real-time updates, integrate LinkedIn's partner Webhooks API (requires
LinkedIn partner access) or run the sync more frequently.

**Multiple accounts**: The LinkedIn client is a module-level singleton. To
support multiple accounts, refactor `_linkedin_client` into a dict keyed by
email and add account selection to the auth flow.

**Persistence across restarts**: The SQLite DB is in `./data/` (Docker volume).
Conversations and drafts persist. LinkedIn session cookies are cached by the
library (see above).
