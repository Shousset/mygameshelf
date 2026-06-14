# Graph Report - .  (2026-06-14)

## Corpus Check
- Corpus is ~19,602 words - fits in a single context window. You may not need a graph.

## Summary
- 328 nodes · 620 edges · 25 communities (16 shown, 9 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.89)
- Token cost: 0 input · 42,428 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Backend API & Steam Sync|Backend API & Steam Sync]]
- [[_COMMUNITY_Frontend Pages & Components|Frontend Pages & Components]]
- [[_COMMUNITY_Games & Sessions API|Games & Sessions API]]
- [[_COMMUNITY_Frontend Dependencies|Frontend Dependencies]]
- [[_COMMUNITY_Game Import & Data Models|Game Import & Data Models]]
- [[_COMMUNITY_System Architecture Overview|System Architecture Overview]]
- [[_COMMUNITY_TypeScript Config|TypeScript Config]]
- [[_COMMUNITY_App Layout & Connection Status|App Layout & Connection Status]]
- [[_COMMUNITY_Dashboard & Loading Skeletons|Dashboard & Loading Skeletons]]
- [[_COMMUNITY_Navigation & Auth Pages|Navigation & Auth Pages]]
- [[_COMMUNITY_API Proxy Middleware|API Proxy Middleware]]
- [[_COMMUNITY_JWT Authentication|JWT Authentication]]
- [[_COMMUNITY_Next.js  Vercel Branding|Next.js / Vercel Branding]]
- [[_COMMUNITY_ESLint Config|ESLint Config]]
- [[_COMMUNITY_Next.js Config|Next.js Config]]
- [[_COMMUNITY_PostCSS Config|PostCSS Config]]
- [[_COMMUNITY_File Document Icon|File Document Icon]]
- [[_COMMUNITY_Globe Icon|Globe Icon]]
- [[_COMMUNITY_Browser Window Icon|Browser Window Icon]]
- [[_COMMUNITY_Library Import Concept|Library Import Concept]]
- [[_COMMUNITY_Offline Degradation|Offline Degradation]]

## God Nodes (most connected - your core abstractions)
1. `get_connection()` - 43 edges
2. `apiFetch()` - 27 edges
3. `compilerOptions` - 16 edges
4. `_run_full_steam_sync()` - 14 edges
5. `get_game()` - 13 edges
6. `menu_games()` - 13 edges
7. `add_game()` - 11 edges
8. `_get_steam_api_key()` - 10 edges
9. `get_user_steam_id()` - 10 edges
10. `list_games()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `FastAPI Backend` --references--> `fastapi dependency`  [INFERRED]
  README.md → requirements.txt
- `FastAPI Backend` --references--> `uvicorn dependency`  [INFERRED]
  README.md → requirements.txt
- `api_get_game()` --calls--> `get_game()`  [EXTRACTED]
  api/main.py → db/models.py
- `api_get_sessions()` --calls--> `get_sessions()`  [EXTRACTED]
  api/main.py → db/models.py
- `api_log_session()` --calls--> `get_game()`  [EXTRACTED]
  api/main.py → db/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **6-Hour Steam Sync Tick Flow** — readme_scheduler_6h, readme_getownedgames, readme_playtime_delta, readme_achievements_sync [EXTRACTED 0.90]
- **Three-Tier Web Architecture** — readme_nextjs_frontend, readme_fastapi_backend, readme_postgresql [INFERRED 0.85]

## Communities (25 total, 9 thin omitted)

### Community 0 - "Backend API & Steam Sync"
Cohesion: 0.06
Nodes (72): AchievementCreate, AchievementToggle, api_add_achievement(), api_dashboard_feed(), api_health(), api_list_achievements(), api_refresh_game(), api_steam_profile() (+64 more)

### Community 1 - "Frontend Pages & Components"
Cohesion: 0.06
Nodes (41): URLS, Variant, STATUSES, Achievement, addAchievement(), addGame(), addWishlistItem(), apiFetch() (+33 more)

### Community 2 - "Games & Sessions API"
Cohesion: 0.14
Nodes (27): api_delete_game(), api_get_game(), api_get_sessions(), api_get_stats(), api_list_wishlist(), api_rate_game(), api_remove_wishlist(), api_update_status() (+19 more)

### Community 3 - "Frontend Dependencies"
Cohesion: 0.07
Nodes (26): dependencies, framer-motion, lucide-react, next, react, react-dom, @supabase/ssr, @supabase/supabase-js (+18 more)

### Community 4 - "Game Import & Data Models"
Cohesion: 0.14
Nodes (21): api_add_game(), api_add_wishlist(), api_import_epic(), api_import_psn(), api_import_steam(), api_list_games(), api_log_session(), BulkImport (+13 more)

### Community 5 - "System Architecture Overview"
Cohesion: 0.12
Nodes (20): Achievements Refresh (schema, progress, rarity), Database Layer (connection, models, schema, seed), external_id Title-Match Backfill, FastAPI Backend, GetOwnedGames Steam Web API Call, Legacy CLI (Rich display helpers), MyGameShelf, Next.js 15 Frontend (+12 more)

### Community 6 - "TypeScript Config"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+11 more)

### Community 7 - "App Layout & Connection Status"
Cohesion: 0.15
Nodes (7): metadata, ConnectionStatus(), Status, OfflineError, SyncStatus, AutoSyncSection(), fmtTime()

### Community 8 - "Dashboard & Loading Skeletons"
Cohesion: 0.18
Nodes (5): CurrentlyPlayingHero(), formatRelative(), CoverCardSkeleton(), StatCardSkeleton(), DashboardFeed

### Community 9 - "Navigation & Auth Pages"
Cohesion: 0.21
Nodes (5): HIDDEN_ON, navItems, Stats, SteamProfile, supabase

### Community 10 - "API Proxy Middleware"
Cohesion: 0.40
Nodes (3): config, CookieToSet, PUBLIC_PATHS

### Community 11 - "JWT Authentication"
Cohesion: 0.50
Nodes (3): get_current_user(), Authentication for MyGameShelf — verifies Supabase-issued JWTs.  Each request mu, FastAPI dependency. Returns the authenticated user's UUID, or raises 401.      U

## Knowledge Gaps
- **70 isolated node(s):** `STATUSES`, `metadata`, `PRIORITIES`, `Status`, `Variant` (+65 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `get_connection()` connect `Backend API & Steam Sync` to `Games & Sessions API`, `Game Import & Data Models`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `initialize_schema()` connect `Backend API & Steam Sync` to `Games & Sessions API`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **Why does `list_games()` connect `Game Import & Data Models` to `Backend API & Steam Sync`, `Games & Sessions API`?**
  _High betweenness centrality (0.005) - this node is a cross-community bridge._
- **What connects `Authentication for MyGameShelf — verifies Supabase-issued JWTs.  Each request mu`, `FastAPI dependency. Returns the authenticated user's UUID, or raises 401.      U`, `MyGameShelf — FastAPI REST Backend (multi-tenant) Run with: uvicorn api.main:app` to the rest of the system?**
  _102 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Backend API & Steam Sync` be split into smaller, more focused modules?**
  _Cohesion score 0.05744888023369036 - nodes in this community are weakly interconnected._
- **Should `Frontend Pages & Components` be split into smaller, more focused modules?**
  _Cohesion score 0.05913461538461538 - nodes in this community are weakly interconnected._
- **Should `Games & Sessions API` be split into smaller, more focused modules?**
  _Cohesion score 0.13793103448275862 - nodes in this community are weakly interconnected._