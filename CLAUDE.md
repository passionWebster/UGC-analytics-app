# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All backend commands run from `backend/` — `pydantic-settings` loads `backend/.env` relative to the process CWD, and `app.main` must be importable.

```bash
# Backend dev server (deps are installed in backend/.venv)
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000   # Windows path in this workspace
# python -m uvicorn app.main:app --reload --port 8000                    # after activating the venv
```

- One-shot launcher: `./scripts/start.sh` / `./scripts/stop.sh` (bash; creates a repo-root `venv/`, writes PIDs to `logs/`).
- Lint / type-check: Ruff and Mypy are configured in `backend/pyproject.toml` (Ruff over `app/`; Mypy only over `app/scraper`), but neither is pinned in `requirements.txt` — `pip install ruff mypy`, then `ruff check app` and `mypy` from `backend/`.
- Tests: none exist in the repo (no pytest setup, no test files; the README roadmap lists unit tests as not yet done). Verify changes by running the services and exercising the API/UI; `npm run build` is the type-check gate the README asks contributors to pass.

```bash
# Frontend (from frontend/)
npm run dev        # Vite dev server on 5173, proxies /api -> localhost:8000
npm run build      # vue-tsc type-check + production build
npm run lint       # ESLint (flat config); npm run lint:fix to autofix
```

- API docs: http://localhost:8000/api/docs. Health: `GET /api/health`.
- SQLite DB: `<repo>/data/ugc_streaming_analytics.db` — an absolute path computed in `backend/app/database.py`, created at startup, independent of CWD. Inspect it with `sqlite3` when debugging data issues.

## Architecture

Two apps: a FastAPI backend (`backend/app/`) and a Vue 3 SPA (`frontend/`), talking over `/api/*` (Vite dev proxy). All persistent state is one SQLite file.

### Backend (`backend/app/`)

- `main.py` — app assembly: CORS, HTTP/exception logging, routers, and startup wiring: `init_database()`, APScheduler (`scheduler.py`), NLP worker pool.
- `routers/` — all HTTP endpoints. `routers/analytics.py` (~1500 lines) holds most read APIs plus an image proxy; responses are plain dicts, usually `{"success": ..., ...}`, and unhandled errors are normalized to `{code, msg, detail, data}` by global handlers in `main.py`. JWT auth dependencies (`get_current_user`, `get_current_admin_user`) are in `auth.py` (python-jose + passlib/bcrypt).
- `crud.py` — `AnalyticsService`, the query/aggregation layer for anime, daily stats, rankings, and recommendations.
- `analytics.py` — danmaku/comment analytics: sentiment timeline, episode timeline bins, wordcloud, character trends, insight cards.
- `ai_service.py` — Doubao (Ark) chat client with a TTL response cache; builds a "project knowledge" corpus from repo files plus keyword RAG snippets and answers `/api/chat`; also `generate_insight` (auto-EDA) and `text_to_sql`.
- `scheduler.py` — APScheduler cron jobs: monthly snapshot (1st, 02:00), TMDB enrichment (daily 03:00, skipped when `TMDB_API_KEY` unset), hourly episode online-viewer recording.
- `tasks.py` + `nlp_worker_pool.py` + `nlp_pipeline.py` — NLP orchestration (below).

Data model (`models.py`): `Anime` (season_id PK), `DailyStats`, `EpisodeStats` (per-episode stats + NLP fields), `DanmuRecord` / `CommentRecord` (raw text + sentiment), `EpisodeAnalysisCache` (per-cid timeline/wordcloud payloads), `TmdbAnimeInfo`, `MonthlySnapshot`, `CrawlLog`, `Ranking`, `User` / `UserFavorite`, `RecommendationStrategyConfig`, `AITelemetry`.

SQLite specifics (`database.py`):
- Engine runs WAL + `synchronous=NORMAL` + `busy_timeout=5000` with a `StaticPool` for multi-threaded access.
- There is no Alembic. Schema = `SQLModel.metadata.create_all` plus hand-rolled incremental migrations in `_add_missing_columns()` (columns) and `_ensure_indexes()` (indexes). **When you add a column to an existing table, append it to the matching `_NEW_*_COLUMNS` list** so existing DBs get the `ALTER TABLE`.
- Scraper writes are serialized with `sqlite_write_lock` (`scraper/runtime.py`).

### Scraper (`backend/app/scraper/`)

`BilibiliBangumiCrawler` (`crawler.py`) is a composition-root façade owning the shared SQLModel session, requests session and HTTP helpers; it instantiates the subservices `anime_sync`, `episode_sync`, `danmaku`, `comments`, which reach shared state via `__getattr__` fallback to the façade. Entry point: `create_crawler(session)`.

Flow: `anime_sync` syncs season lists/details → `episode_sync` syncs episode stats (plus hourly online viewers) → `danmaku` / `comments` fetch danmaku (XML/protobuf, WBI-signed, throttled, history requires `BILIBILI_SESSDATA`) and hot comments, persist to SQLite, then trigger NLP.

Danmaku/comment data is **SQLite-only**: everything (current and history danmaku) lands in `danmu_records` / `comment_records`. The former MongoDB layer (`mongodb.py`, `MONGODB_*` settings, the `pymongo` dependency) has been fully removed — do not reintroduce it.

### NLP pipeline

Crawl → `DanmuRecord` rows → `tasks.enqueue_episode_nlp_task()` → multiprocessing worker pool (`nlp_worker_pool.py`; `spawn` start method, `NLP_WORKER_PROCESSES` default 2, started/stopped in `main.py`), with a local-execution fallback (`NLP_ASYNC_FALLBACK_LOCAL`). `tasks.run_episode_nlp_analysis()` reads the episode's SQLite danmaku, cleans/scores via `nlp_pipeline.py` (jieba keywords/entities using `nlp_user_dict.txt`, SnowNLP sentiment mapped to [-1, 1], spam/noise filtering), and persists per-record NLP fields plus `EpisodeStats` aggregates (`nlp_status`: pending → running → success/failed). The analytics router has a refresh path that re-enqueues episodes whose NLP is missing or stale.

### Frontend (`frontend/src/`)

- `main.ts` — Pinia + Element Plus + router bootstrap.
- `router/index.ts` — lazy-loaded views; guards on `meta.requiresAuth` / `meta.requiresAdmin`.
- `stores/` — Pinia: `auth` (token in `localStorage.access_token`, `isLoggedIn`, `isAdmin`), `ui` (theme), `analytics`.
- `api/` — one module per domain (`auth`/`analytics`/`ai`/`admin`/`userSpace`) over a shared axios instance (`api/axios.ts`) that injects the `Bearer` token, redirects to `/login` on 401, and surfaces errors via ElMessage. `baseURL` is `/api` (`VITE_API_BASE_URL` overrides).
- `views/` — the 8 pages (Home, Status, Overview, Report, Recommendation, PersonalSpace, GenreSelection, Login); charts use `vue-echarts` through `composables/useEcharts.ts`.

### Config & logging

- Settings live in `backend/app/config.py` (pydantic-settings; `.env` template at `.env.example`). Optional integrations degrade gracefully when unset: `DOUBAO_API_KEY` (AI chat), `TMDB_API_KEY` (enrichment), `BILIBILI_SESSDATA` (history danmaku). `SECRET_KEY` must be set for real JWTs.
- Logging is loguru (`logger.py`): repo-root `logs/app.log` and `logs/scraper.log`. Use `app_logger` in the web layer and `scraper_logger` in scraper code.
- Code comments, log messages, and user-facing `message` fields are written in Chinese — match that convention.
