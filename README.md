# GitHub Integration App

A full-stack application integrating Django + DRF backend with Vue 3 + TypeScript frontend, using PostgreSQL for data persistence.

## Project Overview

- **Backend**: Django REST Framework API
- **Frontend**: Vue 3 + TypeScript with Vite
- **Database**: PostgreSQL
- **Infrastructure**: Fully Dockerized with hot-reload support

## Architecture

```
.
├── docker-compose.yml
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── .env.example
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   └── core/
│       ├── __init__.py
│       ├── apps.py
│       ├── models.py
│       ├── urls.py
│       └── views.py
├── frontend/
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── api.ts
│       └── vite-env.d.ts
└── README.md
```

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (v20.10+)
- [Docker Compose](https://docs.docker.com/compose/install/) (v2.0+)

## Quick Start

1. **Clone the repository**

2. **Set up environment variables**
   ```bash
   cp backend/.env.example backend/.env
   ```

3. **Start all services**
   ```bash
   docker compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - Health Check: http://localhost:8000/api/health/

## Services

| Service  | Port | Description               |
|----------|------|---------------------------|
| frontend | 5173 | Vue 3 + Vite dev server   |
| backend  | 8000 | Django REST Framework API |
| db       | 5432 | PostgreSQL database       |

## Development

### Hot Reload

Both frontend and backend support hot reload via Docker volume mounts:

- **Frontend**: Changes to files in `frontend/src/` are immediately reflected
- **Backend**: Django's runserver watches for Python file changes

### Running Migrations

```bash
docker compose exec backend python manage.py migrate
```

### Creating a Superuser

```bash
docker compose exec backend python manage.py createsuperuser
```

### Viewing Logs

```bash
docker compose logs -f
docker compose logs -f backend
```

## API Endpoints

### Health Check
- **GET** `/api/health/`
- Returns: `{ "status": "ok" }`

## Environment Variables

### Backend (`.env`)

| Variable    | Description              | Default |
|-------------|--------------------------|---------|
| DEBUG       | Django debug mode (1=on) | 1       |
| SECRET_KEY  | Django secret key        | -       |
| DB_NAME     | PostgreSQL database name | app     |
| DB_USER     | PostgreSQL username      | app     |
| DB_PASSWORD | PostgreSQL password      | app     |
| DB_HOST     | PostgreSQL host          | db      |
| DB_PORT     | PostgreSQL port          | 5432    |

## Next Steps

- [ ] Google OAuth login
- [ ] GitHub OAuth integration
- [ ] Repository selection
- [ ] Webhook subscriptions
