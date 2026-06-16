# MyGameShelf 🎮

A personal game-library tracker with **automatic Steam sync**: playtime, achievements (with icons and rarity), genres, last-played times, and a "recently played" rail — all stored locally in PostgreSQL.

Built with **FastAPI** (Python) + **Next.js 15** (TypeScript) + **PostgreSQL**, styled with a Steam-classic dark theme.

---

## Features

- 📦 **Collection** — Grid or list view with Steam cover art, status (Backlog / Playing / Completed / Abandoned), rating, hours, genre.
- ⏱ **Sessions** — Manual session log + auto-sync delta sessions from Steam every 6 h. Per-game panel shows last-2-weeks hours, last-played, and a "Refresh from Steam" button.
- 🏆 **Achievements** — Real Steam icons (locked/unlocked variants), real unlock timestamps, global rarity %, header progress bar.
- 📋 **Wishlist** — Prioritized wishlist with platform.
- 📊 **Dashboard** — "Currently Playing" hero card with the most-recently-played game, recent unlocks feed, top-line stats.
- 🔄 **Auto-sync** — Background scheduler runs every 6 h. Manual "Sync now" button on Settings.
- 📥 **Library import** — Steam (auto via Web API), Epic and PSN (bulk-paste).
- 🌐 **Offline graceful degradation** — Connection banner; UI keeps last-known data when the backend or network drops.

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| PostgreSQL | 13+ |

---

## Setup

### 1. Clone and enter the project

```bash
git clone <your-fork-url> mygameshelf
cd mygameshelf
```

### 2. Create the database

```sql
CREATE DATABASE mygameshelf;
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:
- `DB_*` — your local Postgres credentials.
- `STEAM_API_KEY` — get one at <https://steamcommunity.com/dev/apikey> (one server-side key for the whole app; required for any Steam sync feature).

You do **not** put a SteamID in `.env` — it's per-user. Each user links their own
Steam account from **Settings → "Sign in through Steam"** (OpenID), which captures
their SteamID64 automatically. (Their profile must be **Public** for sync to work.)

`.env` is gitignored — never commit it.

### 4. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 5. Install frontend dependencies

```bash
cd web
npm install
cd ..
```

### 6. Run

**One command (recommended) — starts backend + frontend together:**

```powershell
# Windows (PowerShell)
.\start.ps1
```
```bash
# Linux / macOS
./start.sh
```

On first run this creates an isolated Python venv (`.venv`), installs backend
dependencies, runs `npm install` if needed, then launches **uvicorn on :8000**
and **Next.js on :3000** in the same console. Press **Ctrl+C** once to stop both.
This guarantees the backend is reachable whenever the page is loaded. (On Windows
you can also just double-click `start.bat`.)

<details>
<summary>Or run the two processes manually</summary>

**Backend (terminal 1):**
```bash
python -m uvicorn api.main:app --reload --port 8000
```
The database schema is created automatically on first startup.

**Frontend (terminal 2):**
```bash
cd web
npm run dev
```
</details>

Open <http://localhost:3000>.

---

## Project Structure

```
mygameshelf/
├── api/              ← FastAPI backend (sync engine, REST endpoints, APScheduler)
│   └── main.py
├── db/               ← Database layer
│   ├── connection.py ← psycopg2 connection from .env
│   ├── models.py     ← CRUD + sync helpers
│   ├── schema.sql    ← Table definitions
│   └── seed.py       ← Sample data (optional)
├── ui/               ← Legacy CLI display helpers (Rich)
├── web/              ← Next.js 15 frontend
│   ├── app/          ← App-router pages (dashboard, games, sessions, achievements, wishlist, import, settings)
│   ├── components/   ← Sidebar, GameCover, ConnectionStatus, Skeleton
│   └── lib/api.ts    ← Typed API client
├── main.py           ← Legacy CLI entry point
├── requirements.txt
└── .env.example
```

---

## Optional: Seed sample data

```bash
python -m db.seed
```

Inserts a few games, sessions, and wishlist items so you can poke around the UI without importing your real library.

---

## How auto-sync works

Sync runs in a **separate worker process** (`worker.py`), not inside the web
server. The flow:

1. **Enqueue.** On every 6-hour tick the scheduler enqueues one job per user
   into a Postgres-backed queue (`sync_jobs` table); the "Sync now" button
   enqueues a single job and returns immediately (HTTP 202).
2. **Claim.** The worker(s) claim the oldest queued job with
   `SELECT ... FOR UPDATE SKIP LOCKED`, so you can run several workers in
   parallel and no two ever grab the same job. A partial unique index keeps at
   most one active job per user, so duplicate enqueues are harmless.
3. **Run.** For the claimed user, the worker:
   - Hits Steam's `GetOwnedGames` once — builds an `appid → playtime + rtime_last_played` index.
   - For each game with a Steam AppID: logs a session delta, refreshes achievements
     (schema + unlock progress + global rarity), and updates genre + release year
     via the Store API (first sync per game only).
   - Records the run in `sync_runs` and updates `games.last_synced_at`.

The frontend polls `/api/sync/status` to show progress and the final result.
Games imported before the `external_id` column existed get backfilled by title
match on the first sync — no manual fix needed.

### Running the worker

`start.ps1` / `start.sh` launch the worker automatically alongside the API and
frontend. To run it on its own:

```bash
python worker.py
```

Scale by starting more workers (each picks different jobs). If you skip the
worker entirely, jobs simply queue up and run once a worker comes online.

---

## License

Personal project — no license currently attached.
