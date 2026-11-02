# Kalki

The ClearIt study buddy. A small animated boy offers students practice questions rewritten by AI.

AI never runs while a student waits. `kalki-worker` rewrites and verifies questions in the
background, and `kalki-api` serves only `VERIFIED` rewrites. Correct answers always come from the
stored key, never from AI.

## How it works

One code base and one Docker image run in two ways:

| Process | Command | Job |
|---|---|---|
| `kalki-api` | `uvicorn app.main:app` | Serves `/companion-api` through the API gateway |
| `kalki-worker` | `python -m app.worker.main` | Listens to `attempt-submitted-events`, runs jobs, queues free tests daily |

Each question goes through: filter, skip if unchanged, rewrite, code checks, two blind solves,
meaning check. It is saved as `VERIFIED`, or `REJECTED` once its retries run out. Prompts are
Jinja templates in `app/ai/prompts/`.

## API

All endpoints need the gateway's service headers and `X-User-Id`.

| Endpoint | Does |
|---|---|
| `GET /companion-api/next` | Returns `visible` and a question without its answer, or `"prompt": null` |
| `POST /companion-api/prompts/{id}/answer` | Marks `{"selectedOption": "A"}` and returns the result |
| `POST /companion-api/prompts/{id}/skip` | Records a skip and increases the wait |
| `GET /companion-api/settings` | Reads sleep and hide state |
| `PUT /companion-api/settings` | Takes `{"sleepMinutes": 60}` (`0` wakes) and `{"hidden": true}` |

`visible` is false only when Kalki is switched off for the student, they hid him or put him to
sleep, a test is running, or the running-test check failed. Otherwise he strolls along the bottom
of the screen, with or without a question.

## Local setup

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env       # every option is described there
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python -m app.worker.main
```

### With Docker

Start baahubali first, because Kalki joins its Docker network. Kalki has no database container: it
connects to TiDB using the `MYSQL_*` values in `.env`.

```bash
docker compose up -d --build
```

Set `BAAHUBALI_NETWORK` if baahubali's network is not `backend_backend-network`.

## Database

Kalki uses its own `kalki` database and user on the TiDB cluster that baahubali uses. Create them
once before the first deploy. Migrations run when `kalki-api` starts.

```sql
CREATE DATABASE kalki;
CREATE USER 'kalki'@'%' IDENTIFIED BY '<password>';
GRANT ALL ON kalki.* TO 'kalki'@'%';
```

On TiDB Cloud Serverless, usernames carry the cluster prefix, so set `KALKI_MYSQL_USER` to match.

## Deploy

CI publishes `ghcr.io/khaansar/kalki` from `master`. From baahubali:

```bash
docker compose -f docker-compose.production.yml --profile kalki up -d
```

Launch steps:

1. Add `KALKI_SERVICE_SECRET` to baahubali's `.env` before deploying it. The test, attempt and
   payment services do not start without it.
2. Start with `KALKI_ENABLED=false`, then queue existing tests:
   `docker exec kalki-worker python -m app.worker.backfill`
3. Set `KALKI_ENABLED=true` and list a small group in `KALKI_ALLOWED_USER_IDS`.
4. Clear `KALKI_ALLOWED_USER_IDS` to open it to everyone.

## Tracking

```bash
docker exec kalki-worker python -m app.stats
```

Prints the verification pass rate, the answered, skipped and slept counts, and the cost per
verified question.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
```
