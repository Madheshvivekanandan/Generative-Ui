---
name: python-best-practices
description: Python coding standard for the o2c-backend FastAPI service. Load BEFORE writing, modifying, or reviewing any Python code in this repo — anything under o2c-backend/ (app/routes/, app/core/, modules/*/*_service.py, database/models/, alembic/, tests/), or any .py file, FastAPI route, SQLAlchemy model, Pydantic schema, pytest test, or Alembic migration. Includes this repo's structure and Python 3.11 constraints, plus naming, type safety, error handling, logging, security, DB access, async, performance, testing, tooling, and a review checklist.
---

# Python Best Practices (Enterprise Standard)

Opinionated synthesis of Google Python Style Guide, PEP 8/257, FastAPI, SQLAlchemy,
pytest, ruff/black/mypy, OWASP, Clean Architecture, SOLID, and DDD.
When this document conflicts with an existing in-repo convention, **follow the repo
and say so** — see §0 for this repo's overrides.

## 0. This Repo (o2c-backend) — Overrides

The Python backend is `o2c-backend/`. These override the generic guidance below:

- **Runtime is Python 3.11** (`requires-python = ">=3.11"`). PEP 695 syntax
  (`type X = ...`, `class Repo[T]`) is a **syntax error** here — use `TypeAlias`,
  `TypeVar`, and `Generic` instead. `X | None`, `list[str]` are fine.
- **Actual layout** — feature-module oriented, not the layered tree in §2:

  ```
  o2c-backend/
    app/main.py, app/routes/, app/core/, app/middleware/   # HTTP layer + RBAC/security/statuses
    modules/<feature>/                                     # credit, tickets, users, products, …
      <thing>_service.py                                   # business logic
      schemas.py                                           # Pydantic DTOs for that feature
    database/models/, database/enums/, database/base.py    # SQLAlchemy
    alembic/                                               # migrations
    configs/, integrations/, utils/, scripts/, tests/
  ```

- **Follow this structure.** Add a new feature as `modules/<feature>/<name>_service.py`
  + `schemas.py`, and its routes under `app/routes/`. Do **not** introduce an
  `app/services/` or `app/repositories/` tree, and do not restructure existing code.
- **No repository layer exists.** Services query via SQLAlchemy directly, and routes
  currently use `Session`/`select()` too. Treat §11's repository pattern as aspirational:
  keep **new** business logic in a `*_service.py` and keep routes thin, but do not
  refactor existing routes to add a repository layer unless asked.
- Shared status/transition/RBAC logic lives in `app/core/` (`statuses.py`,
  `transitions.py`, `rbac.py`) — reuse it rather than re-deriving status rules.
- Tests live in `o2c-backend/tests/` as `test_us<NNN>_<feature>.py` or
  `test_<feature>.py`, with shared fixtures in `conftest.py`. Match that naming.
- Money is **INR** — see the rupee-formatting convention already in the UI. Use
  `Decimal`, never `float`.
- Verify tooling actually configured in `pyproject.toml`/`pytest.ini` before claiming
  a gate in §16 ran; don't invent a `mypy --strict` gate that this repo hasn't adopted.

## 1. General Philosophy

- **Readability over cleverness.** Code is read far more than written. No one-liner golf.
- **Explicit over implicit.** No hidden globals, no magic monkey-patching, no `**kwargs` pass-through where real parameters belong.
- **Single Responsibility.** One reason to change per function, class, and module.
- **Small units.** If you cannot name it precisely, it does too much.
- **Fail loudly, early.** Validate at boundaries; trust data inside the core.
- **Dependencies point inward.** Domain logic never imports web/DB frameworks.
- **No premature optimization.** Optimize only with a measurement in hand; correctness and clarity first.
- **Delete rather than comment out.** Version control is the archive.
- **Boring is a feature.** Prefer the stdlib and the framework's idiom over a novel abstraction.

## 2. Project Structure

```
app/
  main.py            # ASGI app factory, middleware, router registration only
  api/               # HTTP layer: routers, dependencies, error handlers
    v1/routes/
    deps.py
  services/          # Use cases / business logic. Orchestrates repositories.
  repositories/      # All persistence access. Only layer that touches Session.
  models/            # SQLAlchemy ORM entities (persistence shape)
  schemas/           # Pydantic request/response DTOs (wire shape)
  domain/            # Pure business types, value objects, domain exceptions (no I/O)
  core/              # Settings, logging config, security, constants
  db/                # Engine/session factory, base metadata, migrations/ (Alembic)
  clients/           # Outbound HTTP/queue/third-party adapters
  utils/             # Small, generic, dependency-free helpers
tests/
  unit/  integration/  e2e/  conftest.py  factories/
```

**Layer rules (enforced in review):**

| Layer | May depend on | Must never |
|---|---|---|
| `api` | `schemas`, `services`, `deps` | touch `Session`, ORM models, or SQL |
| `services` | `repositories`, `domain`, `clients` | import FastAPI, `Request`, or `HTTPException` |
| `repositories` | `models`, `db` | contain business rules |
| `domain` | stdlib only | import SQLAlchemy, FastAPI, Pydantic-web concerns |
| `utils` | stdlib | import `app.*` |

- `models` ≠ `schemas`. Never return an ORM object from a route; map to a response schema.
- One module per aggregate/feature, not one per pattern, once a layer exceeds ~10 files
  (`services/orders/`, `services/invoicing/`).

## 3. Naming Conventions

| Kind | Convention | Good | Bad |
|---|---|---|---|
| Module / package | `snake_case`, singular noun | `order_service.py` | `OrderUtils.py`, `helpers2.py` |
| Class | `PascalCase` noun | `CreditLimitPolicy` | `credit_mgr`, `DoStuff` |
| Function / method | `snake_case` verb phrase | `reserve_inventory()` | `inventory()`, `handleIt()` |
| Boolean | `is_/has_/can_/should_` | `is_credit_blocked` | `flag`, `status2` |
| Variable | `snake_case`, domain word | `unpaid_invoices` | `data`, `tmp`, `l`, `res` |
| Constant | `UPPER_SNAKE` at module top | `MAX_RETRY_ATTEMPTS` | `maxRetries` |
| Enum | `PascalCase` class, `UPPER_SNAKE` members | `OrderStatus.AWAITING_CREDIT` | `OrderStatus.s1` |
| Private | leading `_` | `_normalize_gstin()` | `normalizeGSTIN2()` |
| Type alias | `PascalCase` | `type OrderId = int` | `orderid_t` |
| Test | `test_<unit>_<scenario>_<expected>` | `test_reserve_inventory_when_out_of_stock_raises()` | `test_1()` |

- Never shadow builtins (`id`, `type`, `list`, `input`, `dict`).
- Avoid abbreviations except universally known ones (`id`, `url`, `http`, `db`, `gst`).
- Units and currency belong in the name: `timeout_seconds`, `amount_inr_paise`.
- Plural names for collections only.

## 4. Imports

- **Absolute imports only** for first-party code: `from app.services.orders import OrderService`.
  Relative imports are acceptable only inside a tightly-cohesive package (`from .policy import ...`).
- Ordering (ruff/isort enforced): stdlib → third-party → first-party → local. One import per line for modules.
- **No wildcard imports.** `from x import *` is banned, including in `__init__.py`.
- Import modules or explicit names, not "everything from a barrel". Keep `__init__.py` thin;
  re-export a curated public API only, and define `__all__` when you do.
- `if TYPE_CHECKING:` for import-only-for-annotations; combine with `from __future__ import annotations`
  when needed for forward refs.
- **Circular dependencies are a design smell, not an import problem.** Fix by moving the shared
  type into `domain/`, or by depending on a Protocol defined in the inner layer and implemented
  outward. Local (function-scoped) imports are a last resort and must carry a comment saying why.
- No side effects at import time: no DB connections, no network calls, no `load_dotenv()` in library modules.

## 5. Functions

- **Target ≤ 30 lines, ≤ 4 parameters, cyclomatic complexity ≤ 8.** Past that, extract.
- **Type hints are mandatory** on every parameter and return value, including `-> None`.
- Keyword-only for optional/boolean parameters: `def send(*, dry_run: bool = False) -> None:`.
  Never pass a bare boolean positionally.
- **Never use mutable defaults.** Use `None` + in-body default, or an immutable default.
- Return early; avoid deep nesting. Prefer a guard clause over `else`.
- One return type. Don't return `Order | None | bool` — raise instead of returning a sentinel.
- **Prefer pure functions** for calculation; isolate I/O in thin shells ("functional core, imperative shell").
- No output parameters (don't mutate caller-owned arguments) unless the name says so (`_in_place`).

```python
def allocate_credit(
    order: Order,
    profile: CreditProfile,
    *,
    allow_override: bool = False,
) -> CreditDecision:
    """Decide how much credit to grant for an order.

    Args:
        order: Order awaiting credit clearance.
        profile: Customer's current credit standing.
        allow_override: Permit exceeding the sanctioned limit for priority accounts.

    Returns:
        The granted amount and the reason code driving the decision.

    Raises:
        CreditProfileStaleError: If the profile snapshot predates the order.
    """
```

## 6. Classes

- Create a class when behaviour and state travel together, or to satisfy a Protocol/port.
  **A class with one method and no state should be a function.**
- `@dataclass(frozen=True, slots=True)` for value objects; Pydantic `BaseModel` only at
  I/O boundaries (validation/serialization); plain classes for services with injected collaborators.
- **Composition over inheritance.** Inherit only for genuine `is-a` or to implement an ABC.
  Depth ≤ 2. No mixin stacks that share mutable state.
- **Dependency Injection via `__init__`.** Never construct collaborators (sessions, HTTP clients,
  settings) inside a class — accept them. This is what makes tests cheap.
- No God objects: a class over ~200 lines or with >7 public methods is being split.
- `@property` for cheap derived reads only; anything with I/O or cost is a method.
- Define `__repr__` for debuggability; never put secrets in it.

```python
class OrderService:
    def __init__(
        self,
        orders: OrderRepository,
        credit: CreditPolicy,
        events: EventPublisher,
    ) -> None:
        self._orders = orders
        self._credit = credit
        self._events = events
```

## 7. Type Safety

- Annotate everything public. mypy runs in **strict** mode; new code must not add ignores.
- Modern syntax: `list[str]`, `dict[str, int]`, `str | None`, `type Alias = ...` (PEP 695).
  Not `List`, `Dict`, `Optional[str]`, `Union[...]`.
- `X | None` means "genuinely absent". Don't use it to dodge error handling.
- **`Protocol` for ports** (structural typing) instead of ABCs, so the inner layer owns the interface
  and outer adapters satisfy it without importing it.
- Generics via PEP 695: `class Repository[T]: ...`, `def first[T](items: Sequence[T]) -> T | None: ...`.
- `TypedDict` for fixed-shape dicts crossing boundaries (external JSON); `NewType` for IDs
  (`type CustomerId = NewType("CustomerId", int)`) to stop mixing them up.
- `Literal` + `Enum` instead of magic strings. `Final` for module constants.
- **`Any` requires a comment justifying it.** `object` + narrowing, or `cast()` at a single
  well-marked seam, is preferred. `# type: ignore[code]` must name the error code and a reason.
- Narrow with `assert isinstance(...)` only in tests; in production use explicit checks that raise.

## 8. Error Handling

- Define a small exception hierarchy per bounded context, rooted in one app base:

```python
class AppError(Exception):
    """Base for all application errors."""

class DomainError(AppError):
    """Business rule violated — caller's input is semantically wrong."""

class CreditLimitExceededError(DomainError):
    def __init__(self, requested: Decimal, available: Decimal) -> None:
        super().__init__(f"requested {requested} exceeds available {available}")
        self.requested = requested
        self.available = available
```

- **Raise domain exceptions from services; translate to HTTP only in the API layer**
  (`@app.exception_handler`). Services must not know status codes.
- Catch the **narrowest** exception type. `except Exception` is permitted only at a top-level
  boundary (request handler, worker loop, CLI entrypoint) and must log with `exc_info=True` and re-raise or fail the unit of work.
- **Never swallow.** `except: pass` and bare `except:` are banned. If an error is truly
  ignorable, log at `debug` and comment why.
- **Always chain:** `raise OrderNotFoundError(order_id) from exc`. Use `from None` only to
  deliberately hide an internal cause from a caller.
- Error messages: state what failed and the identifying value; **never** include secrets, tokens,
  PII, or raw SQL.
- `try` blocks wrap the smallest possible statement set. Cleanup via `finally` or context managers,
  not duplicated code.
- Retries only for genuinely transient faults, with bounded attempts + jittered backoff + idempotency.

## 9. Logging

- One module-level logger: `logger = logging.getLogger(__name__)`. **`print()` is banned** in
  application code (CLI user-facing output excepted).
- **Structured logging** — key/value extras, not string concatenation, so logs are queryable:
  `logger.info("order_credit_blocked", extra={"order_id": order.id, "shortfall": str(gap)})`.
- Use lazy `%s` formatting (`logger.info("synced %s rows", n)`) — never f-strings in log calls.
- **Correlation IDs**: generate/propagate a request ID in middleware, store in a `ContextVar`,
  inject into every log record via a `logging.Filter`, and forward it on outbound calls
  (`X-Request-ID`).
- **Mask sensitive data** at the logging layer (a redacting filter), not by trusting call sites.
  Never log: passwords, tokens, API keys, full card/bank numbers, OTPs, auth headers, full request bodies.
- Levels: `DEBUG` dev detail · `INFO` business milestones · `WARNING` recoverable/degraded ·
  `ERROR` failed operation needing attention · `CRITICAL` process-level failure. No `INFO` inside loops.
- Configure handlers/format **once** at app startup (`core/logging.py`); libraries and modules
  never call `basicConfig`.

## 10. Security (OWASP)

- **Injection:** parameterized queries / ORM constructs only. Never f-string or `%` user input into
  SQL, shell, LDAP, or template strings. If raw SQL is unavoidable, use `text()` with bound params.
- **Command execution:** `subprocess.run([...], shell=False)` with a list argv. `shell=True`,
  `os.system`, `eval`, `exec`, `pickle.loads` on untrusted data are banned.
- **Secrets:** environment/secret manager only, loaded through a typed `Settings`
  (`pydantic-settings`). **No hardcoded credentials, keys, or connection strings** — not even in
  tests, defaults, or comments. Never commit `.env`. Use `SecretStr` and keep secrets out of
  `repr`/logs/tracebacks.
- **Input validation** at the boundary with Pydantic: exact types, `constr`/`Field` bounds,
  `extra="forbid"`, allow-lists over deny-lists. Validate file uploads by size/type/content, not extension.
- **AuthN:** vetted libraries only. Passwords via Argon2id/bcrypt (never SHA/MD5). JWTs: verify
  signature + `alg` + `aud` + `iss` + `exp`; short TTL; no secrets in the payload. Use `secrets`,
  never `random`, for tokens; compare with `hmac.compare_digest`.
- **AuthZ:** enforce on every endpoint via a dependency; **deny by default**. Check object-level
  ownership/tenancy in the service or repository query (`WHERE tenant_id = :tenant`), not just role —
  IDOR is the default bug otherwise.
- **Output encoding:** let the framework serialize JSON; autoescape templates; never build HTML by
  concatenation. Set security headers and a strict CORS allow-list (no `allow_origins=["*"]` with credentials).
- **Transport & data:** TLS with certificate verification on (never `verify=False`), encrypt sensitive
  data at rest, minimize PII collected and retained.
- **SSRF/path traversal:** validate and allow-list outbound URLs; resolve and confine file paths
  (`Path.resolve().is_relative_to(base)`).
- Generic error responses to clients; details to logs. No stack traces or SQL in API responses;
  `DEBUG=False` in production.
- Pin dependencies with a lockfile; run `pip-audit`/`safety` and `ruff`'s security rules (`S`, i.e. bandit) in CI.

## 11. Database (SQLAlchemy 2.0 + Alembic)

- **Repository pattern:** repositories expose intent-named methods
  (`find_unpaid_by_customer(customer_id)`), return domain/ORM objects, and are the **only** place
  `Session`/`select()` appears. No `Session` in routers or services' signatures beyond passing it to repos.
- **2.0 style:** `select()` + `session.execute(...).scalars()`, `DeclarativeBase` with
  `Mapped[...]` / `mapped_column(...)`. Avoid legacy `Query` and implicit autoflush surprises.
- **Transactions:** one transaction per unit of work, owned by the **service** (or a
  `unit_of_work` context manager) — repositories never commit. Use `with session.begin():` and let
  exceptions roll back. Never `commit()` inside a loop over records.
- **Session lifecycle:** one session per request via a FastAPI dependency
  (`yield` + `finally: close()`); never a module-global session; sessions are not thread/task-safe.
  Configure `pool_size`, `max_overflow`, `pool_pre_ping=True`, `pool_recycle`.
- **Parameterized always.** `text("... WHERE id = :id")` with `{"id": id}`.
- **Relationships:** set `lazy="raise"` (or `raise_on_sql`) by default so N+1 fails loudly; load
  explicitly with `selectinload`/`joinedload`. Always define `back_populates` and an explicit
  `cascade`/`passive_deletes` policy.
- **Concurrency:** use `with_for_update()` or optimistic versioning (`version_id_col`) for
  read-modify-write on money/stock. Make writes idempotent where retries are possible.
- **Migrations:** every schema change ships an Alembic revision, reviewed, with a working
  `downgrade()`. Autogenerate then **hand-edit**. Backfills are separate, batched, idempotent
  migrations/scripts. Expand → migrate → contract for zero-downtime; never rename/drop a column in
  the same release that stops using it. No destructive DDL without an explicit sign-off note.
- Money as `Numeric`/`Decimal` (or integer minor units) — never `float`. Timestamps as timezone-aware UTC.
- Index every foreign key and every column used in a hot `WHERE`/`ORDER BY`; add `UNIQUE`
  constraints for real business keys. Constraints in the DB, not only in Python.

## 12. FastAPI

- **Thin routers.** A handler validates input via schema, calls one service method, returns a
  response model. Target ≤ 15 lines and **zero** business logic, `if` chains, or SQL.
- **Never touch the database from a router.** Route → service → repository, always.
- **Dependency Injection** for session, current user, settings, and services (`Annotated[X, Depends(...)]`).
  Use `dependencies=[Depends(require_role(...))]` at router level for cross-cutting auth.
- **Response models** on every route: `response_model=OrderOut`, `status_code=...`,
  `response_model_exclude_none` where useful. Separate `...In` / `...Out` / `...Patch` schemas —
  never accept the same model you emit, and never expose ORM objects or internal fields.
- Register `@app.exception_handler` for `DomainError`, validation errors, and a catch-all → RFC-7807
  style JSON. Don't scatter `HTTPException` through services.
- `async def` handlers when the work is I/O-bound and awaitable; **plain `def` when the work is
  blocking** (FastAPI runs it in a threadpool) — a blocking call inside `async def` stalls the loop.
- **BackgroundTasks** only for short, fire-and-forget, failure-tolerant work (emails, cache warm).
  Anything retryable, long, or business-critical goes to a real queue/worker.
- Pagination (`limit`/`offset` or cursor) and explicit `max` bounds on every list endpoint.
- Lifespan context manager for startup/shutdown; version the API (`/api/v1`); tag and document routes.
- Middleware for request ID, timing, and error boundary — not for business rules.

## 13. Async Programming

- Async for **I/O-bound concurrency** (HTTP, DB, queues). CPU-bound work goes to
  `ProcessPoolExecutor` or a worker, never inline in the event loop.
- **Never block the loop:** no `time.sleep`, `requests`, blocking DB drivers, or heavy file I/O in
  `async def`. Use `asyncio.sleep`, `httpx.AsyncClient`, async drivers (`asyncpg`), or wrap legacy
  blocking calls in `await asyncio.to_thread(...)`.
- **Don't mix stacks.** One project, one choice: sync SQLAlchemy + sync routes, or `AsyncSession` +
  async routes. `AsyncSession` is not shareable across concurrent tasks.
- Concurrency with `asyncio.TaskGroup` (3.11+) — it propagates errors and cancels siblings.
  `gather(..., return_exceptions=True)` only when you deliberately handle partial failure.
- Never fire-and-forget a bare `asyncio.create_task` — keep a reference, await it, or use a TaskGroup,
  or it gets garbage-collected and its exception vanishes.
- Every outbound call gets a timeout (`asyncio.timeout()` / client timeout). Treat
  `asyncio.CancelledError` as cancellation: clean up and re-raise, never swallow it.
- Reuse one `AsyncClient`/pool for the app lifetime; use `async with` for all async resources.
- Guard shared mutable state with `asyncio.Lock`; use `ContextVar` (not globals) for request-scoped context.

## 14. Performance

- **N+1 is the default bug.** Eager-load with `selectinload`, or fetch parents then children in one
  `IN` query. `lazy="raise"` makes violations impossible to miss.
- Select only the columns you need for wide tables (`select(Order.id, Order.total)`).
- **Bulk operations** for volume: `insert().values([...])`, `session.execute(update(...))`,
  `bulk_insert_mappings`, `COPY` for very large loads. Never a per-row loop with a commit.
- **Pagination everywhere** — keyset/cursor pagination for large or deep result sets (`OFFSET` degrades linearly).
- **Stream, don't accumulate:** generators, `yield`, `session.stream()`/`yield_per()`, chunked file
  reads, `StreamingResponse` for large exports. Never `.all()` an unbounded table into memory.
- **Cache** with an explicit key, TTL, and invalidation story: `functools.lru_cache`/`cache` for pure
  in-process functions, Redis for shared/cross-process. Never cache per-user data under a global key.
- Prefer set/dict lookups over list scans in loops; hoist invariant work out of loops; use
  `__slots__`/frozen dataclasses for high-cardinality objects.
- Measure before optimizing (`cProfile`, `EXPLAIN ANALYZE`, timing logs) and state the numbers in
  the PR. Add an index before adding a cache.

## 15. Testing

- **pytest** only. `tests/` mirrors `app/`. `test_<module>.py`, `test_<unit>_<scenario>_<expected>()`.
- **AAA structure** (arrange/act/assert), one behaviour per test, assert on outcomes not internals.
- **Unit tests** for services/domain: fast, no DB, no network — fake repositories via Protocols.
- **Integration tests** for repositories/migrations/routes: real DB (testcontainers or a disposable
  schema), transaction-rollback fixtures for isolation, `TestClient`/`httpx.ASGITransport` for the app.
- **Mock at the boundary you own** (repository, client interface) — not deep internals, and never
  mock the thing under test. Prefer fakes/stubs over `MagicMock` for anything with behaviour.
  `respx`/`responses` for HTTP; never hit real third parties.
- **Cover the edges:** empty, one, many; boundary values; `None`/missing; duplicates; unicode;
  Decimal rounding; timezone/DST; concurrent update; permission denied; upstream timeout;
  and every raised exception path.
- Deterministic: freeze time (`freezegun`/injected clock), seed randomness, no `sleep`, no ordering
  dependence between tests, no shared mutable module state.
- `pytest.mark.parametrize` instead of copy-pasted cases. Factories/builders (`factory_boy` or plain
  helpers) instead of giant literal fixtures. Markers for `slow`/`integration`.
- **Coverage: ≥ 85% overall, ~100% on services/domain**, and every bug fix ships a regression test
  that fails before the fix. Coverage is a floor, not the goal — assertions matter more than lines.

## 16. Code Quality Gates

Before code is "complete", all of these pass locally and in CI:

```bash
ruff format .                 # formatting (or: black .)
ruff check --fix .            # lint: E,F,I,N,UP,B,S,SIM,C4,RET,ARG,PTH,ASYNC,ANN
mypy app                      # strict: no new ignores, no untyped defs
pytest --cov=app --cov-fail-under=85 -q
pip-audit                     # known CVEs in dependencies
alembic upgrade head          # migrations apply cleanly (+ downgrade tested)
```

- Config lives in `pyproject.toml`; line length 100 (or the repo's existing value). Black/ruff-format
  is the sole authority on formatting — never hand-format or argue with it.
- Pre-commit hooks run format, lint, type-check, and secret detection.
- **Zero warnings, zero skipped tests, zero new `# noqa`/`# type: ignore` without a reason comment.**
  A failing gate is not "unrelated" until proven so.

## 17. Documentation

- **PEP 257 docstrings** (Google style) on every public module, class, and function. Skip only where
  the signature is genuinely self-explanatory and trivial. Imperative mood, one-line summary, then
  `Args`/`Returns`/`Raises` — document every raised exception.
- Docstrings say **why and what contract**; the code already says how. Never restate the signature.
- **Inline comments only for non-obvious rationale** — a business rule, a workaround with a link, a
  deliberate perf trade-off. Delete commented-out code and "TODO" without an owner/ticket.
- Update the README/`docs/` when you add a setup step, env var, command, or service. New env vars are
  documented in `.env.example` in the same change.
- FastAPI: `summary`, `description`, `response_model`, `responses={...}` and schema `Field(examples=...)`
  so OpenAPI is the API doc. Keep it truthful — a stale example is worse than none.
- Record non-obvious architectural decisions as a short ADR in `docs/adr/`.
- Type hints replace type documentation; keep both consistent or drop the prose.

## 18. AI Agent Rules

When writing or modifying Python, the agent **must**:

1. **Read before writing.** Inspect neighbouring modules and match existing patterns, naming, and libraries. The repo's convention beats this document.
2. **Type-hint everything**, including `-> None`. No `Any` without a justifying comment.
3. **Respect the layering.** Route → service → repository. **Never** access the DB from a router, never put business logic in a router or repository, never import FastAPI in a service.
4. **Never bypass the service layer**, even for "just a quick read".
5. **Generate tests with the code** — unit tests for every new branch of business logic, plus a failing-then-passing regression test for every bug fix.
6. **Never invent business rules.** If credit limits, tax treatment, rounding, statuses, or SLAs are ambiguous, **ask** — do not guess and do not silently pick a default.
7. **State assumptions explicitly** in the response when proceeding under uncertainty, and mark them in code with a comment only where they affect behaviour.
8. **Never hardcode secrets, credentials, endpoints, or environment values.** Read from typed settings; add to `.env.example`.
9. **Handle errors deliberately.** No bare `except`, no `pass`, always chain with `from`.
10. **Ship the migration** with any model change; never edit an applied Alembic revision.
11. **Keep changes minimal and focused.** No drive-by refactors, no reformatting untouched files, no renaming public APIs unasked. One logical change per commit, imperative subject line, and no commits unless the user asked.
12. **Preserve backward compatibility** on public APIs and DB schemas; if a break is unavoidable, say so loudly and propose the expand/contract path.
13. **Do not add dependencies** without saying why and confirming; prefer stdlib.
14. **Run the gates** (format, lint, mypy, tests) and report real output. Never claim verification you didn't perform; if a gate fails, say so with the output.
15. **Delete dead code you create**; don't leave scaffolding, debug prints, or `print()` behind.
16. **Flag anything security-relevant** you touch (auth, tenancy, input handling, SQL, file paths, outbound URLs) in the summary.

## 19. Review Checklist

For an AI reviewer. Flag only real defects; cite `file:line` and state the failure scenario.

**Architecture** — layer boundaries respected? DB accessed only from repositories? services free of framework imports? no circular deps? unit sized right (function ≤30 lines, class ≤200)? duplication that should be extracted — or premature abstraction that shouldn't?

**Security** — any string-interpolated SQL/shell/path? secrets or tokens hardcoded or logged? input validated at the boundary with bounds and `extra="forbid"`? authn *and* object-level authz (tenant/owner) enforced on every new endpoint? `verify=False`, `shell=True`, `eval`, `pickle`? errors leaking internals to clients?

**Type safety** — full annotations? new `Any`/`cast`/`# type: ignore` justified? `X | None` handled at every use? mypy strict clean?

**Error handling** — narrowest exception caught? nothing swallowed? chained with `from`? domain errors mapped to HTTP once, in the API layer? messages free of secrets/PII?

**Logging** — no `print`? structured extras, lazy formatting? correlation ID present? sensitive fields masked? level appropriate and not logging inside hot loops?

**Database** — transaction boundary owned by the service, one per unit of work? no commit in a loop? session lifecycle bound to the request? migration included with a real `downgrade`? indexes/constraints for new columns and FKs? `Decimal` for money, UTC-aware datetimes? concurrent-update safety on balances/stock?

**Performance** — N+1 introduced? unbounded query or `.all()` on a large table? missing pagination? per-row loop that should be bulk? cache key/TTL/invalidation sound? large payload streamed?

**Testing** — new logic covered, including error paths and edge cases? tests deterministic (no time/random/sleep/order dependence)? asserting behaviour, not implementation? mocks at owned boundaries only? regression test present for a bug fix?

**Readability** — names precise, domain-accurate, no shadowed builtins? magic numbers/strings replaced by constants/enums? nesting shallow, early returns? dead code, stray debug, commented-out blocks removed?

**Backward compatibility** — public API/response shape/schema changes? nullable-vs-required flips? default behaviour changes? expand/contract path for destructive DDL?

**Documentation** — docstrings on new public surfaces, `Raises` accurate? new env vars in `.env.example`? README/OpenAPI updated? comments explain *why*?

**Linting** — format/ruff/mypy/pytest all green; no new suppressions without a reason.
