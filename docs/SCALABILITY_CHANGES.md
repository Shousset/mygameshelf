# MyGameShelf — Camino a SaaS: registro de cambios de escalabilidad

Este documento registra, paso a paso, los cambios que llevan a MyGameShelf de
"app single-user que corre en local" a un SaaS multi-tenant escalable. Cada
sección corresponde a un bloqueador identificado en el repaso de arquitectura.

Estado general:

| # | Cambio | Estado |
|---|--------|--------|
| 1 | Connection pooling | ✅ Hecho |
| 2 | Sync de Steam a cola de trabajos | ✅ Hecho |
| 3 | Rate-limiting + caché de metadata de Steam | ✅ Hecho |
| 4 | Row-Level Security en Postgres | ✅ Hecho |
| 5a | Modelo de planes + límites (tope de biblioteca) | ✅ Hecho |
| 5b | Billing con Stripe | ⏳ Pendiente |
| 5c | Observabilidad | ⏳ Pendiente |
| + | Extra: Login con Steam (OpenID) | ✅ Hecho |

---

## 1. Connection pooling ✅

**Fecha:** 2026-06-15

### Problema

`db/connection.py::get_connection()` abría una **conexión nueva** a Postgres en
cada llamada y el código la cerraba al terminar:

```python
# ANTES
def get_connection():
    return psycopg2.connect(host=..., dbname=..., ...)  # socket nuevo cada vez
```

`get_connection()` es el nodo más conectado del sistema (43 aristas en el grafo):
se invoca en ~50 sitios. Bajo carga real de SaaS esto agota el límite de
conexiones de Postgres (≈100 por defecto; Supabase free ≈60) con apenas unas
decenas de usuarios concurrentes, y pagar el handshake TCP+TLS en cada request
añade latencia.

### Solución

Se introdujo un **`ThreadedConnectionPool`** (thread-safe, necesario porque
FastAPI corre los endpoints sync en un threadpool y el scheduler corre en su
propio hilo) construido de forma **perezosa** en el primer uso.

La clave para no tocar los ~50 call sites: un proxy transparente
**`_PooledConnection`** que delega todo a la conexión real **excepto `.close()`**,
que en vez de cerrar la conexión la **devuelve al pool**. Así el patrón existente
sigue funcionando sin cambios:

```python
# Este patrón, repetido en todo el código, NO se tocó:
conn = get_connection()
try:
    with conn.cursor() as cur:
        ...
    conn.commit()
finally:
    conn.close()   # ahora devuelve la conexión al pool, no la cierra
```

Detalles de robustez del proxy:

- **Reset de transacción:** antes de devolver al pool, si la conexión quedó con
  una transacción abierta o abortada (p. ej. tras una excepción sin commit), se
  hace `rollback()`. Así el siguiente que tome la conexión no hereda estado sucio.
- **Conexión rota:** si la conexión es inutilizable, se descarta del pool con
  `putconn(conn, close=True)` para que el pool la reemplace.
- **`close()` idempotente:** llamar `close()` dos veces no falla ni devuelve la
  conexión dos veces.
- **`with conn:`** soportado (semántica transaccional de psycopg2) sin cerrar.

### Archivos modificados

- **`db/connection.py`** — reescrito:
  - `_build_pool()` / `_get_pool()` — pool perezoso y thread-safe.
  - `_PooledConnection` — proxy que enruta `.close()` → `pool.putconn()`.
  - `get_connection()` — ahora presta una conexión del pool.
  - `close_all_connections()` — nuevo; cierra el pool entero (para shutdown).
  - `initialize_schema()` — sin cambios de lógica.
- **`api/main.py`**:
  - Import de `close_all_connections`.
  - `on_shutdown()` ahora llama `close_all_connections()` para liberar sockets.
- **`.env.example`** — nuevas variables (todas opcionales, con defaults):
  - `DB_POOL_MIN` (default `1`)
  - `DB_POOL_MAX` (default `10`) — cap de conexiones concurrentes; mantener por
    debajo del límite del proveedor.
  - `DB_SSLMODE` (ej. `require`) — para Postgres gestionado (Supabase/RDS).

### Compatibilidad

- **Cero cambios** en `db/models.py`, ni en los call sites de `api/main.py`.
- Comportamiento local idéntico si no se definen las nuevas variables.
- Importar el módulo **no** abre conexiones (el pool se crea en el primer
  `get_connection()`), igual que antes solo fallaba al usarse sin `DB_PASSWORD`.

### Verificación

- `python -c "import ast; ast.parse(...)"` sobre `connection.py` y `api/main.py` → sintaxis OK.
- Tests unitarios del proxy con pool/conexión simulados (sin BD real):
  1. Camino normal: transacción idle → vuelve al pool, sin rollback; delegación
     de `cursor()`/`commit()` OK; `close()` idempotente.
  2. Transacción abierta → `rollback()` antes de devolver al pool.
  3. Conexión rota → se descarta del pool (`close=True`).
  - Resultado: **ALL PROXY TESTS PASSED**.

### Recomendación de despliegue

Para SaaS en serio, además del pool de la app conviene un **pooler externo**
(PgBouncer o el pooler de Supabase en modo *transaction*) entre la app y
Postgres. El pool de la app reduce el churn por proceso; el pooler externo
multiplexa conexiones entre **múltiples instancias/workers** de la app, que es
lo que de verdad permite escalar horizontalmente.

### Pendiente / nota para el paso 2

Cuando se escale a **varios workers de uvicorn**, recordar que cada worker tiene
su propio pool: el `DB_POOL_MAX` efectivo es `DB_POOL_MAX × nº de workers`.
Dimensionar en consecuencia para no superar el límite del proveedor.

---

## 2. Sync de Steam a cola de trabajos ✅

**Fecha:** 2026-06-15
**Backend de cola elegido:** Postgres con `FOR UPDATE SKIP LOCKED` (cero infra nueva).

### Problema

La sync estaba acoplada al proceso web y no escalaba:

1. **Lock en memoria** (`_sync_lock` + `_syncing_users`, un `set` de Python en
   `api/main.py`) → con varios workers/instancias de uvicorn cada proceso tenía
   su propio set, no se coordinaban y se **duplicaban las syncs**.
2. **`/api/sync/all` corría la sync síncronamente dentro del request** → el
   request HTTP quedaba bloqueado durante minutos, ocupando un hilo del worker.
3. **El `BackgroundScheduler` vivía dentro de la API** y recorría los usuarios
   **en serie** en el mismo proceso → con N usuarios el tick de 6h no termina a
   tiempo, y con varias instancias de API, cada una corría su propio scheduler.

### Solución

Postgres pasa a ser también una **cola de trabajos durable** (sin Redis ni
servicios extra). Tres piezas:

- **Tabla `sync_jobs`** con un **índice único parcial**
  `(user_id) WHERE status IN ('queued','running')`. Garantiza **un único job
  activo por usuario a nivel de BD**, así que encolar desde varias instancias a
  la vez es seguro: los INSERT duplicados se vuelven no-op vía `ON CONFLICT`.
- **`worker.py`** (proceso aparte) reclama el job más antiguo con
  `SELECT ... FOR UPDATE SKIP LOCKED` → **varios workers en paralelo nunca
  toman el mismo job**. Ejecuta `_run_full_steam_sync` y marca el job
  `done`/`error`. Reencola jobs colgados (`reclaim_stale_jobs`) si un worker
  muere a mitad.
- **El scheduler ahora solo encola** (rápido), no ejecuta. El endpoint manual
  encola y responde **202 al instante**; el frontend hace polling de
  `/api/sync/status`.

### Flujo nuevo

```
                 enqueue (ON CONFLICT DO NOTHING)
 scheduler 6h  ─────────────────────────────────►┐
 POST /sync/all ─────────────────────────────────►│  sync_jobs (Postgres)
                                                   │   status: queued
                                                   ▼
 worker.py  ── claim (FOR UPDATE SKIP LOCKED) ──► running ──► done / error
   (×N en paralelo)                                          ▲
 frontend ── GET /api/sync/status (polling) ────────────────┘
```

### Archivos

- **`db/schema.sql`** — nueva tabla `sync_jobs` + índices (único parcial y de poll).
- **`db/migrations/002_sync_jobs.sql`** — migración idempotente para BD existentes.
- **`db/jobs.py`** (nuevo) — API de la cola: `enqueue_sync`, `claim_next_job`,
  `complete_job`, `fail_job`, `get_active_job`, `reclaim_stale_jobs`.
- **`worker.py`** (nuevo) — proceso que drena la cola; escalable horizontalmente.
- **`api/main.py`**:
  - Eliminado el lock en memoria (`_sync_lock`, `_syncing_users`,
    `_try_begin_sync`, `_end_sync`) y el `import threading`.
  - `_scheduled_steam_sync` ahora **encola** un job por usuario.
  - `POST /api/sync/all` → encola y devuelve **202** `{ok, queued, job_id}`
    (antes: ejecutaba síncrono y devolvía el resultado). **409** si ya hay job activo.
  - `GET /api/sync/status` → `in_progress` y `active_job` se leen de `sync_jobs`.
  - `sync_jobs` se crea también en el live-patch de arranque (BD existentes).
- **`web/lib/api.ts`** — `syncAll()` tipado como respuesta de encolado; `SyncStatus`
  con `active_job`.
- **`web/app/settings/page.tsx`** — `handleSync` adaptado al modelo asíncrono;
  polling adaptativo (4s mientras hay job activo, 15s en reposo); botón muestra
  Queuing/Queued/Syncing.
- **`start.ps1` / `start.sh`** — lanzan el worker como tercer proceso.
- **`.env.example`** — `WORKER_POLL_SECONDS`, `WORKER_STALE_MINUTES`.
- **`README.md`** — sección "How auto-sync works" reescrita + cómo correr el worker.

### Cambio de contrato de la API (ojo)

`POST /api/sync/all` ya **no** devuelve el resultado de la sync (`{synced, errors}`);
devuelve `{ok, queued, job_id}` con código **202**. Cualquier cliente que esperara
el resultado síncrono debe pasar a hacer polling de `/api/sync/status`. El
frontend ya se actualizó.

### Verificación

- Sintaxis OK en `api/main.py`, `db/jobs.py`, `worker.py`, `db/connection.py`.
- Import OK de `db.jobs` y de `worker` (que importa `api.main`) vía el venv del proyecto.
- `tsc --noEmit` del frontend: **sin errores**.
- **Test end-to-end contra Postgres real** (BD local `game_backlog`, PostgreSQL 18.1),
  borrando sus filas de prueba al final:
  1. enqueue + dedup (segundo enqueue → None).
  2. `get_active_job` = queued.
  3. claim con SKIP LOCKED → running.
  4. no doble-encolado mientras corre.
  5. complete → done, sin job activo.
  6. re-encolado tras done.
  7. reclaim de job colgado en running → vuelve a queued.
  - Resultado: **ALL QUEUE TESTS PASSED**.

### Deuda técnica / nota para el futuro

`worker.py` importa `_run_full_steam_sync` desde `api.main`, lo que arrastra la
importación de FastAPI/rutas (no arranca el server ni el scheduler, solo importa).
Funciona, pero lo limpio sería **extraer el motor de sync a su propio módulo**
(p. ej. `api/sync_engine.py`) para que el worker no dependa de la capa web. Se
dejó así para mantener este paso de bajo riesgo y no tocar la lógica de sync que
ya funcionaba.

## 3. Rate-limiting + caché de metadata de Steam ✅

**Fecha:** 2026-06-15

### Problema

El cuello de botella físico del SaaS: **una sola `STEAM_API_KEY` compartida**
para todos los usuarios, y Steam la limita a **~100.000 llamadas/día**. La sync
hacía, por cada juego de cada usuario:

- `GetSchemaForGame` — definición de logros (igual para todos los usuarios).
- `GetPlayerAchievements` — progreso del usuario (por-usuario).
- `GetGlobalAchievementPercentages` — rareza global (igual para todos).
- `appdetails` (Store) — género/año (igual para todos).

3 de esas 4 llamadas devuelven datos **idénticos** para cualquiera que tenga el
juego. Con muchos usuarios y juegos populares (CS2, Dota…), se repetían miles de
veces las mismas llamadas → la cuota diaria se agotaba con pocos cientos de
usuarios. Además no había throttle ni reintentos: un pico de 429/5xx tumbaba la
sync sin recuperación.

### Solución

**a) Caché compartida por `appid` (no por usuario).** Tabla `steam_app_cache`
que guarda schema, rareza global y género/año una sola vez por juego, con TTL
por artefacto (schema 30d, rareza 7d, género/año 90d). La primera sync de
cualquier usuario que tenga el juego puebla la caché; el resto la reutilizan.
Una sync que solo necesita el progreso del jugador (logros y rareza ya en caché)
gasta **1 llamada en vez de 3** por juego. Los juegos sin logros se cachean como
`[]` para no re-consultarlos.

**b) Throttle + backoff centralizado** (`api/steam_http.py::steam_get`). Toda
llamada a Steam pasa por aquí y obtiene: intervalo mínimo entre llamadas
(anti-burst), reintentos con backoff exponencial en 429/5xx respetando
`Retry-After`, y conteo de uso. Reemplazó el `time.sleep(1.5)` crudo que había
en el loop.

**c) Presupuesto diario compartido.** Tabla `steam_api_usage(day, calls)` que
todos los workers incrementan. Si se define `STEAM_DAILY_BUDGET` y se alcanza,
`steam_get` lanza `SteamBudgetExceeded` **antes** de llamar, y la sync corta
limpio (los juegos restantes se marcan `deferred` y se retoman en el siguiente
tick) en vez de reventar la cuota. El uso del día se expone en
`/api/sync/status` (`steam_calls_today`) y se muestra en Settings.

### Reducción de llamadas (ejemplo)

100 usuarios, cada uno con el mismo juego de 50 logros, ya cacheado:

```
ANTES:  100 usuarios × 3 llamadas compartidas  = 300 llamadas redundantes /juego
DESPUÉS: 1 vez (poblar caché) + 100 × 1 (player) = 101 llamadas
         → las 200 llamadas compartidas restantes se ahorran (~66% menos)
```

### Archivos

- **`db/schema.sql`** — tablas `steam_app_cache` y `steam_api_usage`.
- **`db/migrations/003_steam_cache.sql`** — migración idempotente.
- **`db/steam_cache.py`** (nuevo) — getters/setters de caché con TTL +
  `record_steam_calls` / `steam_calls_today`.
- **`api/steam_http.py`** (nuevo) — `steam_get` (throttle + backoff + conteo) y
  `SteamBudgetExceeded`.
- **`api/main.py`**:
  - `_sync_one_steam_game` — schema y rareza desde caché; player siempre por red;
    todas las llamadas vía `steam_get`.
  - `_enrich_genre_year` — caché compartida primero; parsea ambos campos para
    poblar la caché aunque el usuario solo necesite uno.
  - `_fetch_steam_appdetails` — usa `steam_get`.
  - Loop del run — quitado el `sleep(1.5)`; corta limpio con `SteamBudgetExceeded`.
  - `/api/sync/status` — expone `steam_calls_today`.
  - Tablas creadas también en el live-patch de arranque.
- **`web/lib/api.ts`** + **`web/app/settings/page.tsx`** — `steam_calls_today` en
  el tipo y una fila "Steam API calls today" en Settings.
- **`.env.example`** — `STEAM_MIN_INTERVAL_MS`, `STEAM_MAX_RETRIES`,
  `STEAM_DAILY_BUDGET`, y TTLs opcionales.

### Verificación

- Sintaxis e imports OK; `tsc --noEmit` del frontend sin errores.
- **Test contra Postgres real** (con cliente HTTP falso), restaurando el
  contador diario y borrando filas de prueba:
  1. caché de schema: roundtrip + lista vacía cacheada + expiración por TTL.
  2. caché de rareza global.
  3. caché de género/año incluyendo entrada con nulls (sigue siendo hit).
  4. contador de uso diario incrementa.
  5. throttle: 2 llamadas espaciadas ≥ intervalo mínimo (0.153s medido).
  6. backoff: 503 → reintenta → 200, cuenta ambas llamadas.
  7. guard de presupuesto: `steam_get` lanza `SteamBudgetExceeded` al superarlo.
  - Resultado: **ALL CACHE/THROTTLE TESTS PASSED**.

### Nota

Los endpoints de perfil/recientes (`GetPlayerSummaries`, `GetRecentlyPlayedGames`)
siguen llamando a Steam directamente en el request (no por `steam_get`), porque
son de bajo volumen y disparados por el usuario. Rutearlos por el throttle queda
como mejora menor opcional.

## 4. Row-Level Security en Postgres ✅

**Fecha:** 2026-06-15

### Problema

El aislamiento entre tenants dependía 100% de que **cada query** incluyera
`user_id` a mano (`db/models.py`). Es correcto hoy, pero una sola query futura
que olvide el filtro filtraría datos entre usuarios — justo en el camino de la
API, donde el daño es máximo (exponer datos de un usuario a otro autenticado).

### Solución — RLS real, no decorativa

RLS como **red de seguridad a nivel de Postgres**: aunque una query olvide el
filtro, la base de datos se niega a devolver filas de otro tenant.

**Dos roles** (`db/migrations/004_roles.sql`):
- `app_web` — NOBYPASSRLS; la **API** se conecta como este rol → RLS se aplica.
- `app_worker` — BYPASSRLS; el **worker** y trabajos cross-user se conectan así
  (necesitan ver todos los usuarios). Sigue protegido por los filtros explícitos.

**GUC de sesión + ContextVar** (compatible con el pool):
- `db/context.py` — `ContextVar current_user_id` (no thread-local: FastAPI corre
  los endpoints sync en un threadpool vía anyio, que **copia** el contexto al
  hilo; por eso funciona).
- `TenantContextMiddleware` (ASGI puro, en `api/main.py`) — setea el ContextVar
  desde el Bearer token en cada request. ASGI puro (no `BaseHTTPMiddleware`) para
  que el ContextVar se propague de forma fiable al threadpool.
- `db/connection.py::get_connection` — en **cada** préstamo del pool ejecuta
  `set_config('app.current_user_id', <uid o ''>, false)` y lo **commitea** de
  inmediato → durable durante el checkout y sin fuga al siguiente que recicle la
  conexión.

**Políticas** (`db/migrations/004_rls.sql`) en las 5 tablas de contenido por
usuario (`games`, `sessions`, `wishlist`, `achievements`, `sync_runs`):
```sql
USING/WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
```
`NULLIF(...,'')` + `missing_ok=true` → si el GUC no está seteado/está vacío,
resuelve a NULL → **cero filas (deny por defecto)**.

**Fuera de RLS a propósito:** `user_profiles` (el scheduler enumera todos los
usuarios con `list_users_with_steam`; solo guarda user_id+steam_id) y las tablas
operativas globales `sync_jobs`, `steam_app_cache`, `steam_api_usage`. Siguen
protegidas por el filtrado a nivel de app.

Los filtros `user_id = %s` de `db/models.py` se **mantienen** (defensa en
profundidad + correctitud en joins).

### Archivos

- `db/migrations/004_roles.sql` (nuevo) — roles `app_web`/`app_worker` + grants.
- `db/migrations/004_rls.sql` (nuevo) — ENABLE+FORCE RLS + política por tabla.
- `db/context.py` (nuevo) — ContextVar de tenant.
- `db/connection.py` — set/commit del GUC en cada `get_connection`.
- `api/auth.py` — `extract_user_id` (no-fatal, para el middleware) + refactor de
  `get_current_user` para reusar `_decode_user_id`.
- `api/main.py` — `TenantContextMiddleware` (ASGI) registrado.
- `.env.example` — guía de roles por proceso (API=app_web, worker=app_worker).

### Verificación

- Sintaxis + imports OK (vía venv).
- **Test end-to-end contra Postgres real** (BD `game_backlog`), aplicando las
  migraciones y borrando filas de prueba al final:
  1. `app_web` con GUC=A ve solo las filas de A.
  2. con GUC=B ve solo las de B.
  3. GUC vacío → cero filas (deny por defecto).
  4. `WITH CHECK` bloquea INSERT de una fila de otro tenant.
  5. `app_web` puede insertar filas propias.
  6. `app_worker` (BYPASSRLS) ve todo.
  7. El pool setea el GUC desde el ContextVar y **no filtra** entre préstamos.
  - Resultado: **ALL RLS TESTS PASSED**.

### Notas de deploy

- RLS se aplica con migraciones ejecutadas por un **owner/superusuario** (no por
  `app_web`, que no es owner). No se mete en el live-patch de arranque.
- En dev con `DB_USER=postgres` (superuser) **RLS queda dormido** (la app sigue
  igual). Para probar RLS localmente, conéctate como `app_web`.
- Costo: una pequeña query `set_config` extra por cada `get_connection`. Aceptable.

## Extra — Login con Steam (OpenID 2.0) ✅

**Fecha:** 2026-06-15

### Objetivo

Que el usuario vincule su cuenta de Steam **sin pegar el SteamID64 de 17 dígitos**:
un botón "Sign in through Steam". NO reemplaza el login de la app (sigue siendo
Supabase) — solo captura y guarda el `steam_id`. Los datos (juegos, logros)
siguen viniendo de la Web API con la key compartida del servidor.

### Flujo

1. Settings → botón → `GET /api/steam/openid/login` (autenticado) devuelve la URL
   de Steam OpenID (`return_to` = `<FRONTEND_URL>/settings`, `realm` = FRONTEND_URL).
   El front hace `window.location = redirect_url`.
2. Steam autentica y redirige de vuelta con params `openid.*` (incluido
   `openid.claimed_id=.../id/<steamid64>`).
3. El front detecta `openid.mode=id_res`, recoge los params y los POSTea a
   `POST /api/steam/openid/verify` **con el Bearer token**.
4. El backend verifica re-enviando los params a Steam con
   `mode=check_authentication` (espera `is_valid:true`), valida que `return_to`
   sea nuestro frontend, extrae el steamid64 y lo guarda con `set_user_steam_id`.
5. El front limpia los params de la URL y refresca.

**Seguridad:** la identidad sale del JWT (sesión del front), nunca de la URL; el
`check_authentication` impide params forjados; `return_to` se pinnea a nuestro
dominio (anti-replay). Sin dependencias nuevas (httpx + regex).

### Archivos

- `api/main.py` — `GET /api/steam/openid/login`, `POST /api/steam/openid/verify`,
  helper `_verify_steam_openid`, constante `FRONTEND_URL`. `/api/sync/status`
  ahora expone `steam_linked`.
- `web/lib/api.ts` — `steamOpenIdLogin`, `steamOpenIdVerify`, `steam_linked` en el tipo.
- `web/app/settings/page.tsx` — botón "Sign in through Steam" + useEffect que
  procesa el retorno de Steam; fila "Steam account: Linked/Not linked".
- `.env.example` — `FRONTEND_URL`.

### Verificación

- Import OK; `tsc --noEmit` sin errores.
- Unit tests de `_verify_steam_openid` (cliente httpx falso): assertion válida →
  extrae steamid; `is_valid:false` → None; `claimed_id` no-Steam → None; `return_to`
  ajeno → None. Builder de la URL de login verificado. **TODOS PASARON.**

---

## 5a. Modelo de planes + límites ✅

**Fecha:** 2026-06-15
**Decisión:** lo único que separa Free de Pro es el **tope de biblioteca**
(Free = 50 juegos, Pro = ilimitado). Sin límites de sync ni wishlist.

### Diseño

- **Límites como DATO, no código.** Tabla `plans(name, max_games, label)` —
  `max_games NULL` = ilimitado. Ajustar el tope es un `UPDATE`, no un deploy.
  Seed: `free`=50, `pro`=NULL.
- Columna `plan` en `user_profiles` (default `'free'`).
- `db/plans.py` — `get_user_plan`, `set_user_plan` (lo usará billing más adelante),
  `count_user_games`, `remaining_game_quota` (None=ilimitado), `get_plan_and_usage`.
  El cupo se calcula del **conteo vivo** de juegos, así siempre es correcto tras
  borrados.
- **Enforcement:**
  - `POST /api/games` → 403 con mensaje de upgrade si el cupo está agotado.
  - Imports Epic/PSN (`_bulk_import`) y Steam → importan **hasta el cupo** y
    reportan cuántos quedaron fuera por el límite (no fallan a la mitad).
- **`GET /api/plan`** → `{plan, max_games, games_used, games_remaining}` para la UI.
- **Frontend:** sección "Plan" en Settings con barra de uso y aviso al acercarse
  o llegar al tope; el 403 ya se muestra vía el manejo de errores de `apiFetch`.

### Interacción con RLS

`count_user_games` consulta `games` (bajo RLS). En el camino de la API
(`app_web` + GUC) cuenta solo los del usuario; el `WHERE user_id=%s` explícito es
la red extra. `plans` es tabla de referencia global (sin RLS); `user_profiles`
tampoco está bajo RLS. Las nuevas tablas heredan los grants vía el
`ALTER DEFAULT PRIVILEGES` de la migración 004.

### Archivos

- `db/schema.sql`, `db/migrations/005_plans.sql`, live-patch de arranque — tabla
  `plans` + columna `user_profiles.plan`.
- `db/plans.py` (nuevo).
- `api/main.py` — `GET /api/plan`, enforcement en `POST /api/games`, `_bulk_import`
  (Epic/PSN) e import de Steam.
- `web/lib/api.ts` — `getPlan` + tipo `PlanInfo`.
- `web/app/settings/page.tsx` — `PlanSection` (tier + barra de uso).

### Verificación

- Sintaxis + imports OK; `tsc --noEmit` sin errores.
- **Test de lógica contra Postgres real** (cap temporal a 3, restaurado a 50):
  cupo inicial, cupo a 0 al llenar, `get_plan_and_usage`, Pro=ilimitado, y
  recálculo del cupo tras borrar. **5/5 PASARON.**
- **Test de integración HTTP contra servidor vivo:** `/api/plan` (free 0/50),
  add bajo el límite → 201, add sobre el cap → **403 con mensaje de upgrade**,
  `/api/plan` reporta lleno. **4/4 PASARON.** (Datos de prueba y cap restaurados.)

## 5b. Billing con Stripe ⏳

_Pendiente. `db/plans.py::set_user_plan` ya es el punto de entrada para que un
webhook de Stripe ascienda/descienda el plan del usuario._

## 5c. Observabilidad ⏳

_Pendiente (logging estructurado, métricas, error tracking)._
