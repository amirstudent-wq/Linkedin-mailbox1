# LinkedIn Mailbox Manager

An AI-powered LinkedIn inbox manager that lets you view, filter, sort, reply to, and auto-draft responses to your LinkedIn messages — with a daily scheduled scan that surfaces unanswered conversations and prepares Claude-generated replies.

---

## Features

| Feature | Description |
|---|---|
| **Inbox view** | All LinkedIn conversations in one clean interface |
| **Filter & Sort** | By unread status, reply status, date, participant name, free-text search |
| **Reply in-app** | Send messages directly from the UI |
| **AI Reply** | One-click Claude-powered reply generation per conversation |
| **Use Cases** | Define personas (e.g. "Sales Outreach", "Partnership Inquiry") that steer AI tone |
| **Daily Scan** | Scheduler runs at a configured time, finds unanswered threads, drafts replies per use case |
| **Draft Review** | Review, approve, dismiss, or send AI drafts from the Drafts sidebar |

---

## Tech Stack

- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS + React Query
- **Backend**: Python FastAPI + SQLite (via SQLAlchemy async)
- **LinkedIn**: [`linkedin-api`](https://github.com/tomquirk/linkedin-api) (unofficial)
- **AI**: Anthropic Claude (claude-sonnet-4-6 for replies, claude-haiku for prompt generation)
- **Scheduler**: APScheduler (cron-based daily scan)
- **Deployment**: Docker + Docker Compose

---

## Quick Start

### 1. Clone & configure

```bash
git clone https://github.com/amirstudent-wq/linkedin-mailbox1.git
cd linkedin-mailbox1
cp .env.example .env
```

Edit `.env` with your credentials:

```env
LINKEDIN_EMAIL=your.email@linkedin.com
LINKEDIN_PASSWORD=your_password
ANTHROPIC_API_KEY=sk-ant-...
DAILY_SCAN_HOUR=8   # UTC hour for the daily AI scan
```

### 2. Run with Docker

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

### 3. Run locally (development)

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env  # fill in credentials
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

---

## Usage

### First run — sync conversations

1. Open http://localhost:3000
2. Check the status bar — it will show whether LinkedIn is connected
3. Click **Sync** in the filter bar to pull your conversations from LinkedIn
4. Conversations appear in the list; click one to open the thread

### Reply to a message

- Type in the composer and press **Enter** (or click the send button)
- Press **✦ (sparkle)** to generate an AI reply — it pre-fills the composer; edit before sending

### Daily AI scan

- Runs automatically at the configured `DAILY_SCAN_HOUR` (UTC)
- Or click **AI Scan** in the filter bar to run immediately
- Open the **AI Drafts** panel (sparkle icon in the left nav) to review drafts
- Each draft shows the AI's reasoning, the proposed reply, and options to **Send** or **Dismiss**

### Use Cases

- Click the **⚙ Use Cases** nav icon to manage reply personas
- Each use case has a name, description, and system prompt that guides Claude's tone
- Set system prompt to `auto` and Claude will generate one from your name + description
- Active use cases are used in the daily scan — one draft per use case per unanswered thread

---

## API Reference

Full interactive docs at http://localhost:8000/docs (Swagger UI).

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/auth/status` | Check LinkedIn connection status |
| `POST` | `/api/messages/sync` | Sync conversations from LinkedIn |
| `GET` | `/api/messages` | List conversations (filterable/sortable) |
| `GET` | `/api/messages/{id}` | Get conversation with full message thread |
| `POST` | `/api/messages/{id}/reply` | Send a reply |
| `POST` | `/api/ai/reply/{id}` | Generate AI reply draft |
| `GET` | `/api/ai/drafts` | List AI drafts |
| `PATCH` | `/api/ai/drafts/{id}` | Update draft status |
| `GET/POST/PATCH/DELETE` | `/api/use-cases` | Manage AI use cases |
| `POST` | `/api/scheduler/run` | Trigger daily scan manually |

---

## Important Notes

> **⚠  LinkedIn Terms of Service**: This app uses an unofficial LinkedIn API library
> ([linkedin-api](https://github.com/tomquirk/linkedin-api)) that accesses LinkedIn
> through session-based authentication. LinkedIn does not officially support this
> access pattern and may rate-limit or block accounts that use it.
> Use responsibly and at your own risk.

- Credentials are stored only in your local `.env` file — never committed to git
- The SQLite database is persisted in the `./data/` directory
- LinkedIn may require 2FA; if authentication fails, check the backend logs

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings from env vars
│   │   ├── database.py          # Async SQLite setup
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── routers/             # API route handlers
│   │   └── services/            # LinkedIn, AI, Scheduler logic
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   ├── components/          # UI components
│   │   ├── services/api.ts      # API client
│   │   └── types/index.ts       # TypeScript types
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── README.md
```
