# AGENTS.md: leaderboard-hld

This file tells coding agents (and humans) what this project is, why it exists, and how to work on it. Read it fully before making changes.

## 1. Purpose

Build a small real-time leaderboard service in Python. It accepts score updates and serves rankings quickly, using Redis sorted sets for live ranking and PostgreSQL as the durable source of truth. The project demonstrates high-level design decisions: where data lives, how caches stay consistent with it, and how the system recovers when the cache is lost.

## 2. Why we are building this

This is a learning and portfolio project, not a production gaming backend.

- **Learn high-level design:** the goal is to understand the trade-offs between a database, a cache, and a derived ranking structure, and to be able to explain them in an interview.
- **Use a real data structure:** Redis sorted sets are the standard way to build rankings. Building one teaches why O(log N) updates and rank lookups matter at scale.
- **Show a rebuildable system:** treating Redis as a derived view of PostgreSQL shows a design habit that matters in real systems: the cache can always be regenerated.
- **Prepare for later projects:** the same caching and consistency reasoning applies to the URL shortener, the distributed cache, and the movie ticketing system.
- **Build on the Python stack:** FastAPI, Redis, and PostgreSQL are common tools for backend services, and this project keeps the focus on design rather than framework features.

## 3. Scope

### In scope
- Submit a score for a user in a given game (and optionally season)
- Get the top N players for a game
- Get one user's rank and score
- Get players around a user (e.g., 5 above and 5 below)
- Rankings update immediately after a score write
- Rebuild the Redis ranking from PostgreSQL on demand
- Per-game and per-season leaderboards
- Basic per-client rate limiting on score submission
- Health endpoint for the API, Redis, and PostgreSQL

### Out of scope (do not build)
- User accounts, login, or OAuth (use a simple API key header only, if any)
- Anti-cheat or score validation beyond basic input checks
- Frontend or UI
- Multi-region replication
- Automatic sharding of rankings (design it in the README, do not implement it)
- Any AI or ML component

## 4. Architecture

```
leaderboard_hld/
  __init__.py
  main.py          # FastAPI app factory and route registration
  config.py        # Settings from environment variables
  api/
    routes.py      # HTTP endpoints, request and response models
    schemas.py     # Pydantic models for requests and responses
  service.py       # LeaderboardService: business rules that coordinate storage
  store/
    base.py        # RankingStore interface (the cache/ranking abstraction)
    redis_store.py # Sorted set implementation
    db.py          # PostgreSQL access (SQLAlchemy models and session)
  rebuild.py       # Rebuild Redis rankings from PostgreSQL
  errors.py        # Domain exceptions
tests/
  test_service.py
  test_redis_store.py
  test_api.py
  test_rebuild.py
  test_concurrency.py
docker-compose.yml # API, Redis, PostgreSQL
Dockerfile
pyproject.toml
README.md
AGENTS.md
```

### Responsibilities

| Component | Responsibility | Must NOT do |
|---|---|---|
| **API layer** | Parse input, validate, call the service, map errors to HTTP codes | Talk to Redis or PostgreSQL directly |
| **LeaderboardService** | Enforce rules (valid scores, tie rule), write to PostgreSQL first, then update Redis | Contain Redis-specific or SQL-specific code |
| **RankingStore (Redis)** | Maintain sorted sets for rankings; answer top-N, rank, and neighbor queries | Be treated as the source of truth |
| **PostgreSQL** | Store every score record and the current best score per user per game | Compute rankings for live reads |
| **Rebuild job** | Recreate all Redis sorted sets from PostgreSQL | Run inside request handling |

### Data model (PostgreSQL)
- **scores:** `id` (bigint, PK), `game_id` (text), `season_id` (text, nullable), `user_id` (text), `score` (bigint), `submitted_at` (timestamptz)
- **best_scores:** `game_id`, `season_id`, `user_id` (composite PK), `score` (bigint), `updated_at`. This table holds the best score per user, which is what the leaderboard ranks.

Index `best_scores` on `(game_id, season_id, score DESC)` for rebuilds.

### Redis key design
- One sorted set per leaderboard: `lb:{game_id}:{season_id or "all"}`
- Member: `user_id`. Score: the user's best score.
- Operations: `ZADD` to set the score, `ZREVRANGE` for top N, `ZREVRANK` plus `ZSCORE` for a user's rank and score, `ZREVRANGE` with offsets for neighbors.
- Keys must be built only in `redis_store.py`. No other module builds key strings.

### API (initial)
| Method | Path | Purpose |
|---|---|---|
| `POST` | `/games/{game_id}/scores` | Submit a score (body: `user_id`, `score`, optional `season_id`) |
| `GET` | `/games/{game_id}/leaderboard?limit=10&season_id=` | Top N players |
| `GET` | `/games/{game_id}/users/{user_id}/rank?season_id=` | One user's rank and score |
| `GET` | `/games/{game_id}/users/{user_id}/neighbors?window=5&season_id=` | Players around a user |
| `POST` | `/admin/games/{game_id}/rebuild` | Rebuild a game's Redis ranking from PostgreSQL |
| `GET` | `/health` | Liveness and dependency checks |

Rank is 1-based. Return `404` for an unknown user in a leaderboard.

## 5. Key design decisions

These are settled. Agents must follow them unless the owner changes this file.

1. **PostgreSQL is the source of truth.** Every accepted score is written to `scores` and `best_scores` before Redis is updated.
2. **Redis is a derived view.** If Redis is empty or wrong, the rebuild job restores it from PostgreSQL. No feature may depend on data that exists only in Redis.
3. **Only the best score counts.** When a new score is lower than the stored best, `best_scores` and Redis keep the higher value. Scores are not added together.
4. **Write order.** The service writes to PostgreSQL in a transaction, then updates Redis. If the Redis update fails after the database commit, the request returns an error that tells the client to retry, and the rebuild job can always repair the drift.
5. **Ties are resolved by earliest achievement.** Two users with the same score: the one who reached it first ranks higher. The best score and its `submitted_at` are stored separately (score as the Redis sorted-set score, timestamp in PostgreSQL and the service), and ties are broken in the service by earliest `submitted_at`. Record this in the README.

## 6. Rules for coding agents

### Code rules
- Python 3.11 or newer.
- Use FastAPI, Pydantic, SQLAlchemy, `redis-py`, and `pytest`. Pin all versions in `pyproject.toml`. Do not add other frameworks.
- Type hints on all public functions and methods.
- Pydantic models for every request and response. Do not return raw dicts from routes.
- No global Redis or database clients created at import time. Create them in the app factory and pass them in.
- Configuration comes from environment variables through `config.py`. No hardcoded hosts, ports, or passwords.
- Raise domain exceptions from `errors.py` in the service. Map them to HTTP status codes only in the API layer.
- Keep functions small. Split any method longer than about 30 lines.

### Design rules
- The API layer never imports Redis or SQLAlchemy session code.
- The service depends on the `RankingStore` interface, not on `redis_store.py` directly, so tests can use an in-memory fake.
- Redis key strings are built only in `redis_store.py`.
- Every write path updates PostgreSQL first, then Redis.
- Rankings must never be computed by scanning PostgreSQL on a read request. Reads use Redis.

### Testing rules
- Unit tests for the service use an in-memory fake `RankingStore`.
- Redis integration tests run against a real Redis (via `docker-compose` or a test container).
- Database tests run against a real PostgreSQL, not SQLite, because the schema uses PostgreSQL-specific types.
- Required test cases:
  - Submitting a lower score does not lower the user's rank.
  - Tie-break order is correct.
  - Top N returns the correct order and length.
  - Neighbors near the top and bottom of the board return fewer rows without error.
  - Rebuild from PostgreSQL produces the same rankings as Redis before the rebuild.
  - Redis failure after a database commit returns an error, and a later rebuild fixes the ranking.
  - Concurrent score submissions for the same user keep the highest score (run in `test_concurrency.py`).
- Run `pytest` before declaring any task done.

### Documentation rules
- README must include: what the project is, how to run it with `docker-compose up`, the API table, the architecture diagram, the data flow for a score submission, the tie-break encoding, and known limitations.
- Document the sharding approach (e.g., per-game or per-region sorted sets) in the README as a design note only.
- Each module starts with a short docstring stating its responsibility.

### Workflow rules
Work in this order. Do not skip ahead:
1. Domain logic with the in-memory fake store: submit score, best-score rule, top N, rank. Tests passing.
2. PostgreSQL models and the write path (`scores`, `best_scores`) with tests.
3. Redis `RankingStore` implementation and integration tests.
4. API routes, schemas, and error mapping, with API tests.
5. Rebuild job and its tests.
6. Rate limiting on score submission.
7. `docker-compose.yml`, Dockerfile, README, and architecture diagram.

After each step, run tests and summarize what changed in one short paragraph.

### Commit rules
- Small commits, one logical change each.
- Commit messages in the form `<area>: <change>` (e.g., `store: add redis sorted set ranking`).

## 7. Things agents must not do

- Do not make Redis the only copy of any score.
- Do not compute rankings by scanning PostgreSQL on a read request.
- Do not add frameworks beyond the ones listed in section 6.
- Do not add AI, ML, or external API calls.
- Do not delete or weaken tests to make them pass. If a test is wrong, explain why in the commit message.
- Do not change the write order in section 5 without updating that section first.
- Do not commit secrets or `.env` files.

## 8. Definition of done

The project is done when all of the following are true:
- `pytest` passes with no skipped tests.
- `docker-compose up` starts the API, Redis, and PostgreSQL, and the health endpoint reports all three as healthy.
- A score submitted through the API appears in the top N and rank endpoints immediately.
- The rebuild endpoint restores Redis from PostgreSQL and returns the same ranking.
- Tie-break order and the best-score rule are covered by tests.
- The README explains the architecture, data flow, tie-break encoding, API, and limitations.
- The owner can explain why PostgreSQL is the source of truth, why Redis is used, and how the system would shard if one leaderboard got too large.

## 9. Decided items

- **Tie-break encoding:** best score and `submitted_at` are stored separately. Redis sorted-set score is the raw best score; ties are broken in the service by earliest `submitted_at`.
- **`season_id`:** optional for all endpoints; when absent, the Redis leaderboard key uses `"all"`.
- **Rate limiting:** 2 score submissions per 2-minute window per client. Client identified by the `X-API-Key` header, falling back to the client IP when the header is missing.
- **Neighbor queries:** clamp at the top and bottom edges (return fewer rows), no wrap-around.
- **Score limits:** no hard maximum; negative scores are valid.
