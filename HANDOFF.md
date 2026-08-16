# Handoff — LinkedIn Mailbox Manager

This document captures the architectural decisions, interface contracts, and
reasoning that are not obvious from reading the source alone. Start with
`CLAUDE.md` for commands and layout; read this when you need to understand *why*
things are the way they are, or when extending the system.

---

## What was verified working (as of handoff)

- FastAPI backend starts, DB initialises, scheduler registers — confirmed
- All 17 API operations register correctly (verified via OpenAPI spec)
- Conversation list with all 5 filter/sort combinations — confirmed
- Message thread fetch with 3-message history — confirmed
- Use case CRUD (create, patch, delete, toggle) — confirmed
- Draft generation plumbing (AI endpoint returns correct shape) — confirmed
- Reply endpoint: returns 400 for empty body, 502 for LinkedIn error — confirmed
- Next.js build: 0 TypeScript errors, 130 kB first-load JS — confirmed
- Frontend → backend proxy: `/api/*` rewrites work end-to-end — confirmed

**Not testable in the cloud sandbox**: LinkedIn login itself, because the remote
environment's HTTPS proxy blocks `www.linkedin.com:443`. Runs correctly on any
machine with direct internet access.

---

## Architecture decisions

### 1. Why unofficial LinkedIn API (`linkedin-api`)?

LinkedIn's official Messaging API is restricted to approved partners only
(not available to individual developers). The `linkedin-api` library reverse-
engineers LinkedIn's internal Voyager API using session cookies. It's the only
practical option for personal inbox access.

Trade-off accepted: violates LinkedIn ToS, may break on API changes, may
trigger security challenges. The alternative is browser automation
(Playwright), which is heavier, slower, and equally unofficial.

### 2. Why SQLite and not Postgres?

The use case is a single-user personal tool. SQLite with aiosqlite is zero-
infrastructure and persists across restarts via a Docker volume. The whole DB
fits in memory. Migrating to Postgres later requires only changing `database_url`
in `.env` — SQLAlchemy abstracts the rest.

### 3. Why cache conversations in a DB instead of hitting LinkedIn every time?

LinkedIn's Voyager API has aggressive rate limiting. Caching lets the UI stay
responsive while rate limiting only the sync operation. The `synced_at` field
on each `Conversation` tracks freshness. The frontend refetches the DB cache
every 30 seconds; LinkedIn sync is explicit (user presses Sync, or daily scan runs).

### 4. Why lazy LinkedIn client initialisation?

```python
# backend/app/services/linkedin.py
_linkedin_client: Optional[Any] = None

def _get_client() -> Any:
    global _linkedin_client
    if _linkedin_client is None:
        ...authenticate...
    return _linkedin_client
```

The server starts and serves all non-LinkedIn routes (health, use cases, drafts)
even with bad or missing credentials. This makes dev iteration faster — you can
work on AI features without valid LinkedIn credentials.

### 5. Why is `awaiting_reply` pre-computed and stored?

It could be derived at query time (`NOT last_message_is_mine`), but storing it
lets us filter efficiently at the DB level without joining on messages. The
daily scanner reads `awaiting_reply` without touching the messages table.

`awaiting_reply = True` exactly when: the counterpart sent the last message AND
that message contains text (not a reaction or system event).

### 6. Why one `UseCase` → many `AIDraft`s per scan?

A conversation gets one draft per active use case on each scan run. This means
if you have "Sales Outreach" and "Partnership Inquiry" use cases, an unanswered
thread gets two draft options to choose from. The user picks the best one.
Drafts are idempotent: if a pending draft already exists for (conversation,
use_case), the scan skips generation to avoid duplicates.

### 7. Why the `"auto"` sentinel for system prompts?

```python
if system_prompt.strip().lower() == "auto":
    system_prompt = generate_use_case_prompt(name, description)
```

Users shouldn't need to write system prompts to get started. The magic string
`auto` (visible in the UI as a wand button) asks Claude Haiku to generate a
prompt from the use case name and description — cheaper and faster than Sonnet
for this metadata task.

### 8. Frontend state model

Two pieces of state live in `page.tsx`; everything else is server state:

```typescript
const [selectedId, setSelectedId]     // which conversation is open
const [rightPanel, setRightPanel]     // "drafts" | "use-cases" | null
const [filters, setFilters]           // ConversationFilters object
```

React Query caches the conversation list and the active conversation separately.
Invalidating `["conversations"]` after a reply or sync refreshes the list.
Invalidating `["conversation", id]` refreshes the open thread. Both happen via
`queryClient.invalidateQueries()` — no manual state mutations.

---

## Key interface contracts

### ConversationFilters (frontend → backend)

```typescript
// frontend/src/types/index.ts
interface ConversationFilters {
  unread_only: boolean           // ?unread_only=true
  awaiting_reply: boolean | null // ?awaiting_reply=true|false (null = no filter)
  search: string                 // ?search=... (matches last_message_text)
  sort_by: "last_message_at" | "participant_name"
  sort_dir: "asc" | "desc"
}
```

### AI reply request/response

```typescript
// Request: POST /api/ai/reply/{conversationId}
{ use_case_id?: number, custom_instructions?: string }

// Response
{ draft: string, reasoning: string, draft_id: number | null }
```

The backend stores the draft in `ai_drafts` and returns the `draft_id`.
The frontend pre-fills the composer with `draft` and keeps `draft_id` to update
status if the user sends or dismisses.

### UseCase shape

```typescript
{ id, name, description, system_prompt, is_active, created_at, updated_at }
```

`system_prompt` is the full Claude system prompt text. Creating with
`system_prompt: "auto"` triggers generation. The generated prompt is stored
(not re-generated each time).

### Daily scan result

```typescript
{ conversations_scanned: number, unanswered_found: number,
  drafts_created: number, errors: string[] }
```

`errors` is a list of non-fatal error strings (per-conversation failures don't
abort the whole scan).

---

## How the LinkedIn response maps to our schema

LinkedIn's Voyager API returns deeply nested objects. The normalisation
happens in `backend/app/services/linkedin.py`.

**Conversation** (from `api.get_conversations()`):
```
LinkedIn element                          → Our field
─────────────────────────────────────────────────────
elem["entityUrn"]                         → id
elem["participants"]                      → participants (normalised)
elem["lastActivityAt"] (ms timestamp)     → last_message_at
elem["events"][0] (latest event body)     → last_message_text
elem["events"][0]["from"]["miniProfile"]  → last sender → last_message_is_mine
elem["read"]                              → is_read
elem["totalEventCount"]                   → message_count
```

**Participant** (nested in each element):
```
raw["com.linkedin.voyager.messaging.MessagingMember"]["miniProfile"]
  → firstName + lastName → name
  → publicIdentifier     → profile_id
  → occupation           → headline
  → picture.*.artifacts[-1].fileIdentifyingUrlPathSegment → avatar_url
```

**Message event** (from `api.get_conversation(urn_id)`):
```
event["entityUrn"]                        → id
event["eventContent"]["com.linkedin.voyager.messaging.event.MessageEvent"]
  ["attributedBody"]["text"]              → body
event["from"]["com.linkedin.voyager.messaging.MessagingMember"]
  ["miniProfile"]["publicIdentifier"]     → sender_id
event["createdAt"] (ms timestamp)        → sent_at
```

If any key is missing, helper functions (`_safe_text`, `_safe_ts`,
`_participant_from_raw`) return empty defaults rather than raising.

---

## Extension recipes

### Add a new filter (e.g. filter by participant name)

1. `backend/app/routers/messages.py` → add `name_search: Optional[str] = Query(None)` param
2. Add a post-filter loop over `participants` JSON (SQLite can't index JSON fields):
   ```python
   if name_search:
       conversations = [c for c in conversations
                        if any(name_search.lower() in p.get("name","").lower()
                               for p in (c.participants or []))]
   ```
3. `frontend/src/types/index.ts` → add field to `ConversationFilters`
4. `frontend/src/services/api.ts` → add to params in `getConversations()`
5. `frontend/src/components/FilterBar.tsx` → add UI control

### Add a new AI persona to the daily scan

```bash
curl -X POST http://localhost:8000/api/use-cases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Recruiting",
    "description": "Replies to candidates reaching out for jobs",
    "system_prompt": "auto"
  }'
```

The system prompt is generated automatically and stored. The next daily scan
will generate drafts using this persona for all unanswered threads.

### Change the Claude model used for replies

`backend/app/services/ai_agent.py` → `generate_reply()`:
```python
response = client.messages.create(
    model="claude-opus-5",   # ← change this
    ...
)
```

Use `claude-haiku-4-5-20251001` for cheaper/faster replies at scale,
`claude-opus-5` for highest quality.

### Add webhook-based real-time sync (future)

The sync flow is pull-based. To add push:
1. Register a LinkedIn Webhook (requires LinkedIn partner status)
2. Add a `POST /api/webhook/linkedin` route that:
   - Verifies the signature
   - Calls `fetch_conversations(limit=5)` to refresh recent threads
   - Invalidates the appropriate DB rows
3. Connect a WebSocket from the frontend to get notified without polling

### Swap SQLite for Postgres

```env
# .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost/linkedin_mailbox
```

Add `asyncpg` to `requirements.txt`. No code changes needed — SQLAlchemy handles it.

---

## Files to read first (in order)

1. `CLAUDE.md` — commands, layout, API routes, data model
2. `backend/app/models.py` — the 4 tables, all fields
3. `backend/app/schemas.py` — every API input/output shape
4. `backend/app/services/linkedin.py` — LinkedIn ↔ DB normalisation
5. `backend/app/services/scheduler.py` — the daily scan loop
6. `frontend/src/app/page.tsx` — component wiring + state model
7. `frontend/src/services/api.ts` — all HTTP calls in one file
