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
- `STEAM_API_KEY` — get one at <https://steamcommunity.com/dev/apikey> (optional, but required for any Steam sync feature).
- `STEAM_ID` — your 17-digit SteamID64 from <https://store.steampowered.com/account> (your profile must be **Public** for sync to work).

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

On every 6-hour tick (and the "Sync now" button), the backend:

1. Hits Steam's `GetOwnedGames` once for all your games — builds an `appid → playtime + rtime_last_played` index.
2. For each game with a Steam AppID:
   - Computes a playtime delta vs the DB and logs a session row if positive.
   - Refreshes achievements: re-fetches schema + your unlock progress + global rarity, then replaces the rows.
   - Updates genre + release year via the public Store API (only on the first sync per game).
3. Records the run in `sync_runs` and updates `games.last_synced_at`.

Games imported before the `external_id` column existed get backfilled by title match on the first sync — no manual fix needed.

---

## License

Personal project — no license currently attached.
