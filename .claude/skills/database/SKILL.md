---
name: database
description: Use when design.md/teaching_brief.md calls for structured (relational/NoSQL) storage — not vector retrieval, that's vector-store's job — and names SQLite, Postgres, or MongoDB. Scaffolds the chosen store's connection, schema/migration, and query calls — never substitutes a different store than the one named.
---

# Database

Covers structured storage (rows/documents, not embeddings) so schema and
query code stays consistent regardless of which store a brief picks. Pairs
with `vector-store` for RAG usecases that also need exact-match/structured
lookups (e.g. Agentic RAG's multi-tool routing, capability #3 in
`agent-agentic-rag`) — the two are separate stores, never conflate them.

## When to use

- Any project/concept/teaching build whose brief/design names structured
  storage: user accounts, transactional records, SQL-queryable tables, a
  document store for semi-structured records. The choice is always
  explicit — never default to one silently if the brief/design didn't name
  it; that's what `clarify-requirements`/`teaching-brief`/
  `agent_system_design_to_build_onego`'s data-store question is for.

## Recommending a default (during interview, not after)

When asked to recommend rather than the user naming one outright, ground
the recommendation in the usecase, not a generic default:

- **SQLite** — local-first, zero external service, file-based. Recommended
  default for teaching/local demos and any single-process app with no
  concurrent-writer requirement. Ships in Python stdlib (`sqlite3`) — no
  new dependency.
- **Postgres** — recommend only when the usecase implies concurrent writers,
  a real multi-client deployment, or relational integrity constraints
  (foreign keys enforced across services) that SQLite's single-writer model
  can't support. Requires `DATABASE_URL` env var — a hard stop if missing,
  same as any other required credential.
- **MongoDB** — recommend only when records are naturally
  document-shaped/schema-variable (e.g. heterogeneous event logs, nested
  JSON with no fixed shape) and relational joins aren't needed. Requires
  `MONGODB_URI` env var — hard stop if missing.

Never recommend Postgres or MongoDB by default over SQLite "for
production-readiness" alone — that's over-engineering for a teaching demo;
only pick them when the usecase concretely needs what SQLite can't do.

## Procedure

1. Confirm which store was chosen — `sqlite`, `postgres`, or `mongodb`. Do
   not substitute; if the brief says Postgres, SQLite is not "close enough"
   once concurrent writes are actually in scope.
2. Add the dependency via `pick-requirements`:
   - SQLite: none beyond stdlib `sqlite3` (or `aiosqlite` if the backend is
     async).
   - Postgres: `psycopg[binary]` (or `asyncpg` for async) + `DATABASE_URL`
     in `.env.example`.
   - MongoDB: `pymongo` (or `motor` for async) + `MONGODB_URI` in
     `.env.example`.
3. Scaffold via `helper-utils`' pattern — one small module (e.g. `db.py`)
   exposing only the operations the app actually needs (e.g. `get(id)`,
   `insert(record)`, `query(filter)`). Callers never touch the driver/ORM
   directly.
4. Schema: SQLite/Postgres need an explicit `CREATE TABLE`/migration
   (a single `schema.sql` or inline `CREATE TABLE IF NOT EXISTS` at
   startup is enough for a demo — no migration framework unless the brief
   asks for one). MongoDB needs no schema, but document the expected shape
   in `data/README.md` anyway so ingestion/query code stays consistent.
5. No mock mode: Postgres/MongoDB calls are real network calls against a
   real instance — if the connection env var is missing or the connection
   fails, that's a hard stop (same treatment as a missing LLM key), not a
   fallback to SQLite. SQLite needs no external service, so it has nothing
   to "mock" — it's real and local by construction.
6. Document in `data/README.md` (or the teaching demo's README): which
   store, the schema/collection shape, and how to reset it (delete the
   local SQLite file, drop/recreate Postgres tables, or drop the MongoDB
   collection) if a demo needs to start from scratch.
