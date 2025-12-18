# GitHub Integration App

A full-stack application integrating Django + DRF backend with Vue 3 + TypeScript frontend, using PostgreSQL for data persistence.

## Current Status: Phase 3 Complete

- [x] Phase 0: Infrastructure (Docker, Django, Vue, PostgreSQL)
- [x] Phase 1: Google OAuth Login
- [x] Phase 2: GitHub OAuth & Repository Selection
- [x] Phase 3: Webhook Subscription & Receiver

## Project Overview

- **Backend**: Django REST Framework API
- **Frontend**: Vue 3 + TypeScript with Vite
- **Database**: PostgreSQL
- **Auth**: Google OAuth (login) + GitHub OAuth (account linking)
- **Webhooks**: GitHub webhook subscription for push and pull_request events

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- Google Cloud Console project with OAuth 2.0 credentials
- GitHub OAuth App

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **APIs & Services** → **Credentials**
4. Click **Create Credentials** → **OAuth client ID**
5. Select **Web application**
6. Add authorized JavaScript origins:
   - `http://localhost:5173`
7. Add authorized redirect URIs:
   - `http://localhost:5173`
8. Copy the **Client ID**

## GitHub OAuth Setup

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Fill in the form:
   - **Application name**: Your app name
   - **Homepage URL**: `http://localhost:5173`
   - **Authorization callback URL**: `http://localhost:5173/auth/github/callback`
4. Click **Register application**
5. Copy the **Client ID**
6. Generate and copy a **Client Secret**

## Quick Start

1. **Set up environment variables**
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   ```

2. **Add your credentials** to `backend/.env`:
   ```bash
   GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
   GITHUB_CLIENT_ID=your-github-client-id
   GITHUB_CLIENT_SECRET=your-github-client-secret
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   WEBHOOK_BASE_URL=https://your-public-url.ngrok.io
   ```

3. **Add Google Client ID** to root `.env`:
   ```bash
   GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
   ```

4. **Run database migrations**
   ```bash
   docker compose up -d db
   docker compose run --rm backend python manage.py migrate
   ```

5. **Start all services**
   ```bash
   docker compose up --build
   ```

6. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000

## Services

| Service  | Port | Description               |
|----------|------|---------------------------|
| frontend | 5173 | Vue 3 + Vite dev server   |
| backend  | 8000 | Django REST Framework API |
| db       | 5432 | PostgreSQL database       |

## API Endpoints

### Health Check
- **GET** `/api/health/`
- Returns: `{ "status": "ok" }`

### Google Authentication
- **POST** `/api/auth/google/`
- Request: `{ "id_token": "google-id-token" }`
- Response: `{ "id": 1, "email": "user@gmail.com", "name": "User Name" }`

### GitHub OAuth
- **GET** `/api/github/oauth/url/`
  - Query: `?user_id=1`
  - Returns: `{ "url": "https://github.com/login/oauth/authorize?..." }`

- **POST** `/api/github/oauth/callback/`
  - Request: `{ "code": "github-code", "user_id": 1 }`
  - Response: `{ "username": "octocat", "github_user_id": 123 }`

- **GET** `/api/github/status/`
  - Query: `?user_id=1`
  - Response: `{ "linked": true, "username": "octocat", "selected_repo": {...} }`

### GitHub Repositories
- **GET** `/api/github/repos/`
  - Query: `?user_id=1`
  - Response: `{ "repos": [{ "id": 123, "name": "repo", "full_name": "user/repo", ... }] }`

- **POST** `/api/github/repos/select/`
  - Request: `{ "user_id": 1, "repo_id": 123 }`
  - Response: `{ "id": 123, "name": "repo", "full_name": "user/repo", "html_url": "...", "webhook_created": true }`

### GitHub Webhooks
- **POST** `/api/github/webhooks/`
  - Receives GitHub webhook events
  - Validates `X-Hub-Signature-256` header
  - Logs event summary
  - Returns: `{ "status": "received" }`

## Webhooks (Phase 3)

### How Webhooks Work

1. When a user selects a repository, the backend automatically creates a GitHub webhook
2. The webhook subscribes to `push` and `pull_request` events
3. GitHub sends events to `POST /api/github/webhooks/`
4. The backend validates the signature and logs the event

### Subscribed Events

| Event | Description |
|-------|-------------|
| `push` | Triggered on git push to any branch |
| `pull_request` | Triggered on PR open, close, merge, etc. |

> **Note**: There is no separate "merge" event in GitHub. Merges are detected via `pull_request` events where `action=closed` and `merged=true`.

### Event Processing

⚠️ **Events are NOT processed** — they are only:
- Validated (signature check)
- Parsed (extract event type and summary)
- Logged
- Acknowledged (200 OK)

This is intentional for Phase 3. Event processing would be added in a future phase.

### Local Testing with ngrok

GitHub webhooks require a publicly accessible URL. For local development:

1. **Install ngrok**
   ```bash
   # macOS
   brew install ngrok
   
   # Or download from https://ngrok.com/download
   ```

2. **Start ngrok tunnel**
   ```bash
   ngrok http 8000
   ```

3. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.io`)

4. **Update `backend/.env`**
   ```bash
   WEBHOOK_BASE_URL=https://abc123.ngrok.io
   ```

5. **Restart the backend**
   ```bash
   docker compose restart backend
   ```

6. **Select a repository** — the webhook will be created with the ngrok URL

### Webhook Signature Validation

All incoming webhooks are validated using HMAC SHA-256:

1. GitHub signs the payload with your `GITHUB_WEBHOOK_SECRET`
2. The signature is sent in `X-Hub-Signature-256` header
3. Backend recomputes the signature and compares
4. Invalid signatures return `401 Unauthorized`

## Environment Variables

### Root (`.env`)

| Variable         | Description                        | Required |
|------------------|------------------------------------|----------|
| GOOGLE_CLIENT_ID | Google OAuth Client ID (frontend)  | Yes      |

### Backend (`backend/.env`)

| Variable              | Description                   | Required |
|-----------------------|-------------------------------|----------|
| DEBUG                 | Django debug mode (1=on)      | No       |
| SECRET_KEY            | Django secret key             | Yes      |
| DB_NAME               | PostgreSQL database name      | No       |
| DB_USER               | PostgreSQL username           | No       |
| DB_PASSWORD           | PostgreSQL password           | No       |
| DB_HOST               | PostgreSQL host               | No       |
| DB_PORT               | PostgreSQL port               | No       |
| GOOGLE_CLIENT_ID      | Google OAuth Client ID        | Yes      |
| GITHUB_CLIENT_ID      | GitHub OAuth Client ID        | Yes      |
| GITHUB_CLIENT_SECRET  | GitHub OAuth Client Secret    | Yes      |
| GITHUB_WEBHOOK_SECRET | Secret for webhook signatures | Yes      |
| WEBHOOK_BASE_URL      | Public URL for webhooks       | Yes      |

## Database Schema

### AppUser
| Field      | Type         | Description              |
|------------|--------------|--------------------------|
| id         | BigInt (PK)  | Auto-generated ID        |
| google_sub | String (UK)  | Google's unique user ID  |
| email      | String       | User's email             |
| name       | String       | User's display name      |
| created_at | DateTime     | Record creation time     |
| updated_at | DateTime     | Last update time         |

### GitHubAccount
| Field          | Type        | Description                 |
|----------------|-------------|-----------------------------|
| id             | BigInt (PK) | Auto-generated ID           |
| user           | FK (1:1)    | Reference to AppUser        |
| github_user_id | BigInt (UK) | GitHub's user ID            |
| username       | String      | GitHub username             |
| access_token   | String      | OAuth access token (secret) |
| created_at     | DateTime    | Record creation time        |
| updated_at     | DateTime    | Last update time            |

### GitHubRepository
| Field       | Type        | Description                    |
|-------------|-------------|--------------------------------|
| id          | BigInt (PK) | Auto-generated ID              |
| user        | FK          | Reference to AppUser           |
| repo_id     | BigInt      | GitHub's repository ID         |
| name        | String      | Repository name                |
| full_name   | String      | Full name (owner/repo)         |
| html_url    | URL         | GitHub URL                     |
| is_selected | Boolean     | Whether this repo is selected  |
| created_at  | DateTime    | Record creation time           |

### GitHubWebhook
| Field       | Type        | Description                    |
|-------------|-------------|--------------------------------|
| id          | BigInt (PK) | Auto-generated ID              |
| repository  | FK (1:1)    | Reference to GitHubRepository  |
| webhook_id  | BigInt (UK) | GitHub-assigned webhook ID     |
| created_at  | DateTime    | Record creation time           |

## Development

### Running Migrations

```bash
docker compose exec backend python manage.py migrate
```

### Viewing Logs

```bash
docker compose logs -f
docker compose logs -f backend
```

### Rebuilding After Changes

```bash
docker compose up --build
```

### Testing Webhooks Locally

```bash
# Terminal 1: Start ngrok
ngrok http 8000

# Terminal 2: Watch backend logs for webhook events
docker compose logs -f backend | grep WEBHOOK
```

## Architecture

```
.
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── .env.example
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── core/
│       ├── models.py      # AppUser, GitHubAccount, GitHubRepository, GitHubWebhook
│       ├── urls.py
│       └── views.py       # Auth, GitHub API, Webhook views
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts        # Vue app + Google OAuth plugin
│       ├── App.vue        # Login + GitHub UI
│       └── api.ts         # API client
└── README.md
```

## Project Complete

All phases implemented:

1. ✅ **Phase 0**: Docker infrastructure with Django, Vue, PostgreSQL
2. ✅ **Phase 1**: Google OAuth login with user persistence
3. ✅ **Phase 2**: GitHub OAuth account linking and repository selection
4. ✅ **Phase 3**: GitHub webhook subscription and receiver (no event processing)
