# GitHub Integration App

Full-stack webhook integration demo: Django + DRF backend, Vue 3 + TypeScript frontend, PostgreSQL.

## Quick Start

```bash
# 1. Set up environment files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. Edit both .env files with your credentials (see Environment Variables section)

# 3. Start services
docker compose up --build

# 4. Open http://localhost:5173
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend       │────▶│   PostgreSQL    │
│   Vue 3 + TS    │     │   Django + DRF  │     │                 │
│   :5173         │     │   :8000         │     │   :5432         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        │                       │
        ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  Google OAuth   │     │  GitHub API     │
│  (login)        │     │  (OAuth+Webhooks)│
└─────────────────┘     └─────────────────┘
```

### Why These Choices

| Choice | Rationale |
|--------|-----------|
| **Django + DRF** | Battle-tested, excellent ORM, fast API development |
| **Vue 3 + TypeScript** | Reactive UI, type safety, single-file components |
| **Frontend-first OAuth** | Google SDK handles popup/redirect, backend validates tokens |
| **User-triggered webhooks** | Explicit control, clear scope requirements, no background magic |
| **Raw payload storage** | Maximum flexibility, no data loss, easy debugging |

### Data Flow

1. **Login**: Frontend uses Google SDK → Backend validates token → Creates/updates AppUser
2. **GitHub Link**: Frontend redirects to GitHub → Backend exchanges code → Stores scopes + token
3. **Webhook Setup**: User clicks "Setup Webhook" → Backend creates webhook via GitHub API
4. **Event Receipt**: GitHub POSTs to `/api/github/webhooks/` → Backend validates signature → Stores raw payload

## Environment Variables

Each service has its own `.env` file. No root `.env` needed.

### Backend (`backend/.env`)

```bash
# Django
DEBUG=1
SECRET_KEY=change-me-in-production

# Database (must match docker-compose db service defaults)
DB_NAME=app
DB_USER=app
DB_PASSWORD=app
DB_HOST=db
DB_PORT=5432

# Google OAuth (for server-side token validation)
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com

# GitHub OAuth
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret

# Webhooks
GITHUB_WEBHOOK_SECRET=any-random-string
WEBHOOK_BASE_URL=http://localhost:8000
```

### Frontend (`frontend/.env`)

```bash
# Google OAuth (for browser-side Sign-In button)
VITE_GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
```

> **Note**: `VITE_*` variables are exposed to the browser. Never put secrets here.
> 
> For webhook testing, set `WEBHOOK_BASE_URL` in backend/.env to your ngrok URL.

## Testing

### Run Unit Tests

```bash
docker compose exec backend pytest core/tests.py -v
```

Tests cover:
- Google OAuth: token validation, user creation/update
- GitHub OAuth: code exchange, scope persistence
- Webhook receiver: signature validation, duplicate handling, event storage
- Webhook setup: scope checks, reuse/create logic

### Test Webhooks Locally

1. Start a tunnel:
   ```bash
   ngrok http 8000
   # or
   cloudflared tunnel --url http://localhost:8000
   ```

2. Update `WEBHOOK_BASE_URL` in `backend/.env`:
   ```bash
   WEBHOOK_BASE_URL=https://abc123.ngrok.io
   ```

3. Restart backend:
   ```bash
   docker compose restart backend
   ```

4. Select a repository → webhook created with public URL

5. Push to your repo → events appear in the UI

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/` | GET | Health check |
| `/api/auth/google/` | POST | Google token validation |
| `/api/github/oauth/url/` | GET | Get GitHub OAuth URL |
| `/api/github/oauth/callback/` | POST | Exchange code for token |
| `/api/github/status/` | GET | Get link status + scopes |
| `/api/github/repos/` | GET | List public repos |
| `/api/github/repos/select/` | POST | Select a repository |
| `/api/github/webhooks/setup/` | POST | Create/reuse webhook |
| `/api/github/webhooks/events/` | GET | List stored events |
| `/api/github/webhooks/` | POST | Webhook receiver (GitHub calls this) |

## Tradeoffs & Intentional Limitations

| What | Why |
|------|-----|
| **No background jobs** | Keeps infrastructure simple; webhook receiver is synchronous |
| **No event processing** | Demonstrates integration, not business logic |
| **No JWT/session auth** | Stateless design; user_id passed per request for simplicity |
| **No GitHub App** | OAuth App is simpler for this use case |
| **No private repos** | Would require additional scopes and consent handling |
| **Raw payload storage** | No derived fields—preserves all data for future use |

### Why No Merge Event?

GitHub doesn't have a separate `merge` event. Merges are detected via:
```
pull_request event where action=closed AND merged=true
```

### Why Signature Validation Matters

Without signature validation, anyone could POST fake events to your endpoint. The HMAC-SHA256 signature proves the payload came from GitHub.

## Future Improvements

If this were a production system:

1. **Event Processing Queue**
   - Celery/SQS for async processing
   - Idempotent consumers keyed by delivery_id
   - Retry with exponential backoff

2. **Auth Improvements**
   - JWT tokens with refresh
   - Session management
   - CSRF protection for sensitive endpoints

3. **Webhook Resilience**
   - Dead letter queue for failed processing
   - Event replay capability
   - Rate limiting

4. **GitHub App Migration**
   - Installation-based auth
   - Fine-grained permissions
   - Multiple repos per installation

5. **Observability**
   - Structured logging
   - Metrics (Prometheus)
   - Distributed tracing

## Project Structure

```
.
├── docker-compose.yml
├── backend/
│   ├── .env.example      # Backend env template
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── config/
│   │   └── settings.py
│   └── core/
│       ├── models.py     # AppUser, GitHubAccount, GitHubRepository, GitHubWebhook, GitHubWebhookEvent
│       ├── views.py      # All API views
│       ├── urls.py
│       └── tests.py      # Unit tests
└── frontend/
    ├── .env.example      # Frontend env template (VITE_* only)
    ├── Dockerfile
    └── src/
        ├── App.vue       # Main UI
        └── api.ts        # API client
```

## OAuth Setup

### Google

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Web application)
3. Authorized JavaScript origins: `http://localhost:5173`
4. Copy Client ID

### GitHub

1. [GitHub Developer Settings](https://github.com/settings/developers) → New OAuth App
2. Homepage URL: `http://localhost:5173`
3. Callback URL: `http://localhost:5173/auth/github/callback`
4. Copy Client ID and generate Client Secret

### Required GitHub Scopes

| Scope | Purpose |
|-------|---------|
| `read:user` | Fetch profile |
| `repo` | List repositories |
| `admin:repo_hook` | Manage webhooks |

Users missing `admin:repo_hook` see a re-authorization prompt.
