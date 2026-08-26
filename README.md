# OptiMapper

OptiMapper is a full-stack travel itinerary planner. A user chooses a city and a trip length, the backend asks Claude for points of interest, geocodes them with OpenStreetMap's Nominatim service, groups nearby places into days with K-Means, and orders each day's stops with a nearest-neighbor route heuristic. The resulting itinerary is displayed on an interactive Leaflet map.

Deployed in: https://optimapper.vercel.app/ Might not work

## Features

- AI-generated points of interest for trips from 1 to 14 days
- City and country disambiguation in the planning form
- Nominatim geocoding with rate-limit-aware requests
- Geographic day grouping with K-Means
- Per-day stop ordering based on Haversine distance
- Interactive Leaflet maps and day-by-day itinerary views
- Optional Supabase persistence with an in-memory fallback
- Responsive Vue and Vuetify interface

## Tech stack

| Area | Technologies |
| --- | --- |
| Frontend | Vue 3, Vite, Vuetify, Vue Router, Axios, Leaflet |
| Backend | Python 3.11, FastAPI, Uvicorn/Gunicorn, Anthropic SDK |
| Optimization | scikit-learn, NumPy, Haversine distance |
| Data | Supabase/PostgreSQL, with in-memory fallback |
| Geocoding | OpenStreetMap Nominatim |

## How it works

1. The frontend sends a city and number of days to `POST /itinerary`.
2. Claude returns approximately seven suggested places per day.
3. Nominatim resolves each place to latitude and longitude.
4. K-Means divides the geocoded places into daily geographic clusters.
5. A nearest-neighbor heuristic orders the stops within each day.
6. The API stores the itinerary in Supabase when configured, or in memory otherwise.
7. The frontend renders the saved route with Leaflet and OpenStreetMap tiles.

## Repository structure

```text
optimapper/
|-- backend/                 # FastAPI application and route-generation services
|   |-- models/              # Pydantic request/response models
|   |-- services/            # Claude, geocoding, and optimization logic
|   `-- Dockerfile           # Production backend container
|-- database/sql/            # Supabase/PostgreSQL schema
`-- frontend/                # Vue/Vite single-page application
    `-- src/
        |-- router/          # Client-side routes
        |-- views/           # Landing, planning, and map pages
        `-- plugins/         # Vuetify configuration
```

## Prerequisites

- Python 3.11+
- Node.js `20.19+` or `22.12+`
- An Anthropic API key
- Optional: a Supabase project for persistent itineraries

## Local setup

### 1. Backend

From the repository root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install the dependencies and create the local environment file:

```bash
pip install -r requirements.txt
cp .env.example .env
```

On Windows PowerShell, use `Copy-Item .env.example .env` instead of `cp` if needed. Set the required values in `backend/.env`, then start the API:

```bash
uvicorn main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

### 2. Database (optional)

Run [`database/sql/create_itineraries_table.sql`](database/sql/create_itineraries_table.sql) in the Supabase SQL editor. The application also reads and writes a `number_of_days` integer column, so ensure that column exists in `optimapper.itineraries` in your deployed schema.

If Supabase is not configured, newly generated itineraries are stored in backend memory and are lost when the server restarts.

### 3. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The Vite development server prints the local frontend URL when it starts.

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | Yes | Authenticates requests to Claude. |
| `SUPABASE_URL` | No | Supabase project URL used for persistence. |
| `SUPABASE_KEY` | No | Supabase key used only by the backend. |
| `PORT` | No | Runtime port; defaults to `8080` when `main.py` is run directly. |

`SUPABASE_URL` and `SUPABASE_KEY` must be provided together. Without both, the API uses its in-memory store.

### Frontend (`frontend/.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | Yes | Base URL of the OptiMapper backend, such as `http://localhost:8000`. |

> [!IMPORTANT]
> Vite exposes every `VITE_*` value to browser code. `VITE_API_URL` is intentionally public; never put API keys, database credentials, or other secrets in a `VITE_*` variable.

The real `.env` files are ignored by Git. Commit only the provided `.env.example` files, which contain placeholders rather than credentials.

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | API status and usage hint |
| `POST` | `/itinerary` | Generate and save an itinerary |
| `GET` | `/itinerary/{id}` | Retrieve a saved itinerary |
| `GET` | `/itineraries/random` | Return up to three recent random itineraries |

Example request:

```bash
curl -X POST http://localhost:8000/itinerary \
  -H "Content-Type: application/json" \
  -d '{"city":"Madrid, Spain","days":3}'
```

## Production builds

Build the frontend with:

```bash
cd frontend
npm run build
```

Build the backend container with:

```bash
docker build -t optimapper-api ./backend
docker run --env-file backend/.env -p 8080:8080 -e PORT=8080 optimapper-api
```

Set `VITE_API_URL` to the deployed API URL before building the frontend. Review the backend's permissive CORS configuration before exposing a production deployment.

## Security notes

- Never commit `.env` files or real credentials; the repository-wide ignore rules cover common environment, key, certificate, and local tooling files.
- Keep Anthropic and Supabase credentials on the backend. Only `VITE_API_URL` belongs in the frontend environment.
- Use a least-privilege Supabase key and appropriate Row Level Security policies.
- If a credential is ever committed, revoke or rotate it first, then remove it from the entire Git history. Deleting it only from the latest commit is not sufficient.
- Avoid logging credential values, including partial prefixes or suffixes.

## License

No license file is currently included. Unless a license is added, all rights are reserved by the repository owner.
