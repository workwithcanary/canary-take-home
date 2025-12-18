# GitHub Integration App

A full-stack application integrating Django + DRF backend with Vue 3 + TypeScript frontend, using PostgreSQL for data persistence.

## Current Status: Phase 1 Complete

- [x] Phase 0: Infrastructure (Docker, Django, Vue, PostgreSQL)
- [x] Phase 1: Google OAuth Login
- [ ] Phase 2: GitHub OAuth integration
- [ ] Phase 3: Repository selection & Webhooks

## Project Overview

- **Backend**: Django REST Framework API
- **Frontend**: Vue 3 + TypeScript with Vite
- **Database**: PostgreSQL
- **Auth**: Google OAuth (frontend-initiated, backend-verified)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)
- Google Cloud Console project with OAuth 2.0 credentials

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

## Quick Start

1. **Set up environment variables**
   ```bash
   cp .env.example .env
   cp backend/.env.example backend/.env
   ```

2. **Add your Google Client ID** to both `.env` files:
   ```bash
   # Root .env (for docker-compose → frontend)
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   
   # backend/.env (for Django backend)
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   ```

3. **Run database migrations**
   ```bash
   docker compose up -d db
   docker compose run --rm backend python manage.py migrate
   ```

4. **Start all services**
   ```bash
   docker compose up --build
   ```

5. **Access the application**
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

## Auth Flow (Phase 1)

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Browser │────▶│ Google  │────▶│ Frontend│────▶│ Backend │
└─────────┘     └─────────┘     └─────────┘     └─────────┘
     │               │               │               │
     │  Click Login  │               │               │
     │──────────────▶│               │               │
     │               │               │               │
     │  OAuth Popup  │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │  ID Token     │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │               │  Send Token   │               │
     │               │──────────────▶│               │
     │               │               │               │
     │               │               │  Verify Token │
     │               │               │──────────────▶│
     │               │               │               │
     │               │               │  User Data    │
     │               │               │◀──────────────│
     │               │               │               │
     │  Logged In    │               │               │
     │◀──────────────────────────────│               │
```

## Environment Variables

### Root (`.env`)

| Variable         | Description                        | Required |
|------------------|------------------------------------|----------|
| GOOGLE_CLIENT_ID | Google OAuth Client ID (frontend)  | Yes      |

### Backend (`backend/.env`)

| Variable         | Description              | Required |
|------------------|--------------------------|----------|
| DEBUG            | Django debug mode (1=on) | No       |
| SECRET_KEY       | Django secret key        | Yes      |
| DB_NAME          | PostgreSQL database name | No       |
| DB_USER          | PostgreSQL username      | No       |
| DB_PASSWORD      | PostgreSQL password      | No       |
| DB_HOST          | PostgreSQL host          | No       |
| DB_PORT          | PostgreSQL port          | No       |
| GOOGLE_CLIENT_ID | Google OAuth Client ID   | Yes      |

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
│       ├── models.py      # AppUser model
│       ├── urls.py
│       └── views.py       # HealthCheck, GoogleAuth
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts        # Vue app + Google OAuth plugin
│       ├── App.vue        # Login UI
│       └── api.ts         # API client
└── README.md
```

## Next Steps

- [ ] GitHub OAuth integration
- [ ] Repository selection
- [ ] Webhook subscriptions
