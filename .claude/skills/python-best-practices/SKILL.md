---
name: python-best-practices
description: Python standard for the Gen_Ui generative-UI backend — a flat FastAPI service that streams LLM-planned dashboard blocks to the browser as A2UI v0.9 messages over SSE. Load BEFORE writing, modifying, or reviewing any Python in this repo (backend/main.py, agent.py, a2ui.py, schemas.py, session.py, baseline.py, mock_data.py, or any new .py file). Covers the two-contract design (typed blocks vs A2UI wire), the streaming double-pass, sanitize(), the never-error stream rule, error/secret hygiene, naming, typing, logging, tests, and a review checklist.
---

# Python Best Practices — Gen_Ui backend

Adapted from Google's Python Style Guide, PEP 8/257, FastAPI docs, ruff/mypy, and OWASP,
then cut down to what this service actually is. **When this document conflicts with the
existing code, follow the code and say so.**

## 0. This project — what it is and is not

```
backend/
  main.py            # app assembly only: env, logging, CORS, include routers
  api/               # HTTP layer: health.py, dashboard.py, generate.py (one router each)
    streams.py       #   SSE framing + the per-turn stream; CANVAS_SURFACE lives here
  agent/             # the streaming loop, one concern per module:
    runner.py        #   optimistic + authoritative passes (run, _generate)
    prompts.py       #   SYSTEM_PROMPT (built once at import, on purpose)
    fallbacks.py     #   FALLBACK_COPY + fallback()
    emit.py  follow_ups.py  events.py  config.py
  a2ui/              # A2UI v0.9 wire format:
    messages.py      #   envelope builders + bind()
    sanitizer.py     #   sanitize() + text_note()
    compiler.py      #   _VIEW, compile_block, group_children, component_tree, full_surface
    constants.py     #   VERSION, CATALOG_ID, REFINE_ACTION, MAX_*
  schemas/           # ONE Pydantic model PER FILE; __init__.py re-exports them all
  session.py         # per-session rolling transcript (one class: SessionStore)
  baseline.py        # the load-time dashboard, built from the same blocks + compiler
  mock_data.py       # the fixed dataset + its plain-text rendering for the prompt
  tests/             # pure-function tests: sanitizer, compiler, follow-ups, session window
  pyproject.toml     # tool config (pytest pythonpath, ruff); deps mirrored in requirements.txt
  requirements.txt  .env.example  Dockerfile  .dockerignore
```

**House rules for structure:** one class per file (the owner's standard — see
`schemas/`), one concern per module, and every package `__init__.py` re-exports its
public names so callers write `import a2ui` / `from schemas import LineChart` without
caring which file something lives in. Imports point one way — `main → api → agent →
a2ui → schemas`, with `session`, `baseline` and `mock_data` as leaves. Keep new files
small and focused; do not add service layers, repositories, or persistence without
being asked.

Deliberately absent — **do not add these without being asked**:

| Not here | Why |
|---|---|
| Database, SQLAlchemy, Alembic | No persistence. Sessions are an in-memory LRU; a restart is a fresh conversation. |
| Repository / service layers | Seven small modules with a linear import graph ARE the structure. |
| Auth, users | Single-user demo. |
| `async def` routes | The OpenAI SDK call is blocking; plain `def` handlers return sync generators that Starlette iterates in its threadpool. **Do not convert routes to `async def` while the client is synchronous.** |

Runtime is `python:3.12-slim` in Docker and 3.14 locally. Use `X | None`, `list[str]`,
`Literal`, and the `|` union operator. Dependencies are range-pinned in
`requirements.txt` (mirrored in `pyproject.toml` — change both together); **`openai` is
held at `<2`** because the code uses `client.beta.chat.completions.stream`.

## 1. The two contracts that define this service

Everything else is detail. Get these wrong and nothing works.

### Contract A — two schemas, on purpose

`schemas.py` carries the **block catalog**: Pydantic models that are simultaneously

1. the JSON Schema handed to OpenAI as `response_format`, which **constrains what the
   model can emit** (constrained decoding, not instruction-following), and
2. the validator every parsed block passes before it is compiled.

The model never speaks A2UI. `a2ui.py` compiles validated blocks into genuine A2UI v0.9
messages (`createSurface`, `updateDataModel`, `updateComponents`); nothing downstream of
that module knows about block types. Consequences, all enforced in review:

- **`Block` is a bare union of `Literal`-tagged models.** Do not add a Pydantic
  `Field(discriminator=...)` — that emits a `discriminator` keyword OpenAI's strict schema
  mode rejects. The `Literal["line_chart"]` tag on each member is what does the work.
- **Every catalog field needs a `description`.** It is prompt text; the model reads it.
- **Avoid `Optional`/defaults inside catalog models.** Strict mode marks every property
  required; prefer a required field with a documented "0 if unknown" convention.
- **Adding a block type is exactly three edits**: a model in `schemas.py`, a row in
  `_VIEW` in `a2ui.py`, and a component registered in the frontend catalog. If a change
  needs more, it is wrong.
- Structured outputs guarantee **types and required props, not counts** — "1–4 blocks"
  and "exactly 3 follow-ups" are enforced post-hoc (`blocks[:MAX_BLOCKS]`,
  `clean_follow_ups`). Don't claim the schema enforces them.

### Contract B — the stream never errors

`/api/generate` and `/api/action` return an SSE stream that **never carries an error
status**. Every failure — missing key, upstream error, refusal, validation failure,
all-blocks-unusable — resolves to a `text_note` block with `fallback: true`, emitted
through the same `_emit_blocks` path as real content.

- All failure copy lives in `FALLBACK_COPY`, keyed by a `Literal` ErrorCode. Generic
  prose only (see §3).
- **This is a deliberate deviation** from "log and re-raise at the boundary". It is the
  product requirement. Keep it, and keep the `logger.exception` call.
- Request-shape errors are the exception: Pydantic validation still yields 422, because a
  malformed request is a client bug, not a model failure.

### The streaming double-pass (do not collapse it)

`agent.run()` streams every turn **twice**: optimistically from partial-parse snapshots
(a block is only provably finished once the next one has started — the N−1 rule), then
authoritatively once the stream closes, re-sending the full validated data model and
tree. Replace-wins is what makes the optimistic pass safe. Both passes go through
`sanitize()`; do not "optimize away" either one. Every turn re-composes the single
canvas surface (`CANVAS_SURFACE`), and the client clears it first — see the README's
"One canvas, on purpose".

## 2. `sanitize()` — shape is not sense

Structured outputs guarantee the *shape*. They cannot guarantee four series instead of
nine, a donut with more than one positive slice, or a table row whose cell count matches
its columns. `sanitize()` in `a2ui.py` enforces meaning:

- **Trim what is trimmable** (`MAX_SERIES`, `MAX_POINTS`, `MAX_SLICES`, `MAX_ROWS`,
  `MAX_ACTIONS`), **raise `ValueError` on what is not.** The caller drops that one block
  and keeps the turn.
- Every limit is a module-level `UPPER_SNAKE` constant, and the same numbers appear in
  `SYSTEM_PROMPT` (which interpolates them). **Change both together** or the prompt
  starts lying to the model.
- Keep it pure and synchronous — no I/O, no logging of user content.

## 3. Secrets and error hygiene (the rule most easily broken here)

- **Never put an exception message in anything user-visible.** Fallback copy is generic
  prose keyed by a `Literal` code — never `str(exc)`. An OpenAI `AuthenticationError`
  string contains a partial API key, and fallback bodies render verbatim in the browser.
  Details go to `logger.exception`, which is not user-visible. This repo's first
  security fix was exactly this leak; the regression test asserts no fallback body
  carries exception text.
- `OPENAI_API_KEY` comes from the environment only. **Never** a default, a literal, a
  test fixture, or a comment. `.env` is gitignored; every new variable is documented in
  `backend/.env.example` **and** `compose.yaml` in the same change.
- CORS stays an explicit allow-list from `ALLOWED_ORIGINS`. Never `["*"]`.
- User message text is bounded (`max_length=2000`) and `extra="forbid"` on request
  models. Action context values re-enter generation as user text — bound them the same
  way.

## 4. Naming, typing, functions

| Kind | Convention | Here |
|---|---|---|
| Module | `snake_case`, singular | `mock_data.py` |
| Class | `PascalCase` noun | `DonutChart`, `SessionStore` |
| Function | `snake_case` verb phrase | `clean_follow_ups()`, `compile_block()` |
| Constant | `UPPER_SNAKE`, module top | `MAX_SLICES`, `CANVAS_SURFACE` |
| Private | leading `_` | `_emit_blocks` |

- **Type-hint every parameter and return**, including `-> None`. Modern syntax only:
  `list[str]`, `str | None`, `A | B`. Not `List`, `Optional`, `Union[...]`.
- `Literal` over magic strings — it is both a type and a prompt constraint here.
- Functions ≤ 30 lines, ≤ 4 parameters. Guard-clause early returns over nesting.
- Never shadow builtins (`id`, `type`, `input`, `list`).

## 5. Errors, logging, imports

- Catch the **narrowest** type. `except Exception` only at the generation boundary in
  `agent.run()`, and it must `logger.exception(...)` and yield a fallback.
- No bare `except`, no `except: pass`. Chain with `from exc` when re-raising.
- One module logger: `logger = logging.getLogger("genui")`. **No `print()`.**
- **Lazy `%s` formatting in log calls**, never f-strings: `logger.warning("bad: %s", exc)`.
- Absolute imports, stdlib → third-party → local, one per line. No wildcards.
- Import-time work is confined to `main.py` (`load_dotenv()`) and `agent.py`
  (`SYSTEM_PROMPT`, built once **on purpose** — it embeds the whole dataset and should
  not be re-rendered per request). `schemas.py`, `a2ui.py`, `session.py` and
  `mock_data.py` must stay importable in a test with no environment.

## 6. FastAPI

- **`response_model` on every non-streaming route.** Streaming routes return
  `StreamingResponse` with `media_type="text/event-stream"` and must send
  `X-Accel-Buffering: no` (nginx's `proxy_buffering off` is the other half — the
  belt-and-brace pair that keeps the progressive render alive).
- Thin handlers: validate, call, return. The streaming logic lives in `agent.py`.
- `summary=` on routes so `/docs` is usable.
- Plain `def` handlers — see §0.
- The API is unversioned (`/api/...`) because there is exactly one client. Version it
  when a second appears.

## 7. Testing

`backend/tests/` covers the pure functions — that is where the bugs are:

- `test_a2ui.py`: `sanitize()` edges (trims, one-slice donut, ragged rows, empty series
  raise), `group_children` row packing, `compile_block` bindings and the refine-action
  context, `full_surface` ordering (data before components).
- `test_agent.py`: `clean_follow_ups` (echo drop, casefold dedupe, length cap).
- `test_session.py`: pair-trimmed window, oldest-first eviction, history-returns-a-copy.

Rules: **never call the real OpenAI API in a test** — the streaming loop is exercised by
running the app, not by mocking the SDK's event objects. `python -m pytest` from
`backend/` (pythonpath is configured in `pyproject.toml`). Deterministic, no network, no
sleeps. New pure logic ships with tests; a bug fix ships a failing-then-passing test.

## 8. Gates — honest baseline

```bash
cd backend
python -m pytest -q        # 22 tests, all pure -- must stay green
ruff check .               # config in pyproject.toml (if ruff is installed)
```

There is no mypy gate and no coverage target yet. `requirements.txt` is range-pinned,
not a lockfile. Beyond the tests, the real verification is running the app and hitting
the endpoints — **exercise the endpoint you changed and report the actual output.**
Never claim a gate you did not run.

## 9. AI agent rules

1. **Read `schemas.py` first, then `a2ui.py`.** The block catalog defines what the model
   can say; the compiler defines what the browser receives.
2. **Keep the three-edit rule** (§1A): schema model + `_VIEW` row + frontend catalog
   component, always together.
3. **Keep prompt constants and code constants in sync** (§2).
4. **Never widen what reaches the client.** No exception text, no key material, no stack
   traces in any emitted payload (§3).
5. **Preserve the never-error stream.** A new failure mode needs a new ErrorCode +
   `FALLBACK_COPY` entry, not a raised exception.
6. **Do not collapse the two streaming passes**, and do not emit the last block of a
   partial snapshot (the N−1 rule exists because that block may still be growing).
7. Type-hint everything; no `Any` without a justifying comment.
8. Never hardcode secrets, model names, or endpoints — environment plus a documented
   default, added to `.env.example` and `compose.yaml` together.
9. Do not add dependencies, layers, async, or a database without asking. The value of
   this codebase is that it is small.
10. **Run the tests and what you changed; report real output.** Keep the diff focused;
    no commits unless asked.

## 10. Review checklist

**Catalog** — new block has a `Literal` type tag, a description on every field, a `_VIEW`
row, and a frontend component? Discriminator keyword accidentally introduced? Counts
claimed as schema-enforced when they are post-hoc?

**Stream contract** — every new failure path resolves to a fallback block through
`_emit_blocks`? Anything that can now raise out of `agent.run()`? Both passes still go
through `sanitize()`?

**Secrets & errors** — any `str(exc)`, `{exc}`, or upstream text in an emitted payload?
New env var missing from `.env.example` or `compose.yaml`? CORS still an allow-list?
Action context still bounded?

**Sanitize** — limits enforced as constants, mirrored in the prompt? Unusable output
raising rather than shipping a broken block?

**Typing** — full annotations, modern syntax, no `Optional`/`Union[...]`/`Any`?

**Logging** — lazy `%s`, no f-strings, no `print`, `logger.exception` on the boundary
catch, no user content or secrets logged?

**FastAPI** — streaming route still plain `def` returning a sync generator?
`X-Accel-Buffering: no` intact? handler thin?

**Tests** — pure-function changes covered? tests deterministic, no network?

**Docs** — docstring says *why*? README updated for new setup steps or variables?
