# OptiMapper

OptiMapper builds feasible day-by-day travel plans from verified places, visit durations, opening hours and travel times. Google Places discovers attractions and resolves Claude's editorial suggestions. A time-budgeted planner assigns and orders visits, reserving breaks, a safety margin and hotel transfers when supplied. Without Google credentials, Claude + Nominatim remains available with explicit travel estimates.

## Features

- Trips from 1 to 14 days, with optional start date, interests, pace and accommodation
- City and country disambiguation in the planning form
- Nominatim geocoding with rate-limit-aware requests
- Daily schedules that respect visit duration, known opening hours, breaks and time budgets
- Bounded Google Route Matrix usage; uncovered transfers are clearly marked as estimated
- Required visits, optional alternatives, and controls to remove or assign visits to a day
- Google Maps for Google Places trips; Leaflet/OpenStreetMap for Nominatim trips
- Optional Supabase persistence with an in-memory fallback
- Responsive Vue and Vuetify interface

## Tech stack

| Area | Technologies |
| --- | --- |
| Frontend | Vue 3, Vite, Vuetify, Vue Router, Axios, Leaflet |
| Backend | Python 3.11, FastAPI, Uvicorn/Gunicorn, Anthropic SDK |
| Optimization | Feasible insertion, geographic seeding and local search in Python |
| Data | Supabase/PostgreSQL, with in-memory fallback |
| Places and routing | Google Places API (New), Google Routes API; Nominatim fallback |

## How it works

1. The frontend sends the destination, dates, time budget and preferences to `POST /itinerary`.
2. Google independently discovers popular attractions; Claude optionally supplies editorial suggestions and estimated visit durations. No Google provider content is sent to Claude.
3. Candidates are resolved to actual places and deduplicated. Unresolved required places are reported.
4. A preliminary schedule identifies useful travel pairs. Routes calls are capped at 100 elements by default, rather than querying an unbounded N² matrix.
5. The planner schedules visits within available time and known opening hours, accounting for breaks, waits, buffer and accommodation return. Unsuitable visits remain optional alternatives.
6. The API saves a versioned plan in Supabase or memory. Google content is fetched live by place ID when a saved plan is reopened; raw Places data is not persisted.
7. The diary shows times, daily totals, uncertainties and editable preferences. Replanning saves a new plan and preserves the original.

The planner is a deterministic heuristic; it does not guarantee a global optimum or that every required visit will fit. Opening hours can change, and visit durations are estimates. This version supports walking and driving, not timed ticket reservations or departure-time-dependent public transport. Map connections are schematic, not turn-by-turn routes.

For API activation, credentials, **Cloud Run setup and cost estimates**, follow [the Google Cloud guide](docs/google-cloud-setup.md).

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
- A Google Maps Platform server key and browser key, or an Anthropic API key for the Nominatim fallback
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
| `ANTHROPIC_API_KEY` | For fallback | Editorial suggestions; optional when Google is configured. |
| `ANTHROPIC_MODEL` | No | Claude model; defaults to `claude-sonnet-4-6`. |
| `ENABLE_AI_SUGGESTIONS` | No | Set `false` for Google-only discovery with no Anthropic requests. Defaults to `true`. |
| `ALLOWED_ORIGINS` | No | Comma-separated frontend origins allowed by CORS; defaults to local Vite origins. |
| `GOOGLE_MAPS_API_KEY` | No | Private server key for Places API (New) and Routes API. Enables Google discovery. |
| `GOOGLE_ROUTES_MAX_ELEMENTS` | No | Maximum billed matrix elements per operation; default `100`, `0` skips Routes. |
| `SUPABASE_URL` | No | Supabase project URL used for persistence. |
| `SUPABASE_KEY` | No | Supabase key used only by the backend. |
| `PORT` | No | Runtime port; defaults to `8080` when `main.py` is run directly. |

`SUPABASE_URL` and `SUPABASE_KEY` must be provided together. Without both, the API uses its in-memory store.

### Frontend (`frontend/.env`)

| Variable | Required | Purpose |
| --- | --- | --- |
| `VITE_API_URL` | Yes | Base URL of the OptiMapper backend, such as `http://localhost:8000`. |
| `VITE_GOOGLE_MAPS_API_KEY` | For Google maps | Public browser key restricted by website and to Maps JavaScript API. |
| `VITE_GOOGLE_MAP_ID` | No | Production JavaScript map ID; development defaults to `DEMO_MAP_ID`. |

> [!IMPORTANT]
> Vite exposes every `VITE_*` value to browser code at build time. The Google browser key is intentionally public and must be restricted. Never put the private server key, database credentials, or other secrets in a `VITE_*` variable.

The real `.env` files are ignored by Git. Commit only the provided `.env.example` files, which contain placeholders rather than credentials.

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | API status and usage hint |
| `POST` | `/itinerary` | Generate and save an itinerary |
| `GET` | `/itinerary/{id}` | Retrieve a saved itinerary |
| `POST` | `/itinerary/{id}/replan` | Recalculate exclusions, required visits and day assignments into a new saved plan |
| `GET` | `/itineraries/random` | Return up to three recent random itineraries |

Example request:

```bash
curl -X POST http://localhost:8000/itinerary \
  -H "Content-Type: application/json" \
  -d '{"city":"Madrid, Spain","days":3,"start_date":"2026-11-01","daily_hours":8,"pace":"balanced","travel_mode":"WALK","must_visit":["Museo del Prado"]}'
```

Replanning accepts `excluded_ids`, `must_visit_ids` and `day_assignments` (place ID to day number, starting at 1). Explicit day assignments are prioritized and cannot bypass feasibility. The response includes `day_summaries`, `unscheduled`, `warnings`, provider information and the saved planning `options`. Old `{city, days}` requests and historical itineraries remain supported.

## Tests

No live credentials, paid requests or database writes are needed:

```bash
cd backend
python -m unittest discover -s tests -v
```

```bash
cd frontend
npm ci
npm test
npm run build
```

Coverage includes closed weekdays, overnight hours, special closures, time balancing, hotel return, mandatory visits, geographic grouping, provider outages, matrix cost caps, persistence without raw Google content, historical data, form submission and diary recalculation.

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
- Keep Anthropic and Supabase credentials on the backend.
- Keep the private Maps server key on the backend; the separate, restricted browser key belongs in the frontend.
- Use a least-privilege Supabase key and appropriate Row Level Security policies.
- If a credential is ever committed, revoke or rotate it first, then remove it from the entire Git history. Deleting it only from the latest commit is not sufficient.
- Avoid logging credential values, including partial prefixes or suffixes.

## License

No license file is currently included. Unless a license is added, all rights are reserved by the repository owner.
