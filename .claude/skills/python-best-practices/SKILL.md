---
name: python-best-practices
description: Python standard for the Gen_Ui generative-UI backend — a single-module FastAPI service that turns a free-text message into one LLM-chosen, schema-validated dashboard component. Load BEFORE writing, modifying, or reviewing any Python in this repo (backend/main.py, backend/schemas.py, backend/mock_data.py, or any new .py file). Covers the component-catalog contract, structured-output calls, the never-500 fallback rule, error/secret hygiene, naming, typing, logging, Docker, and a review checklist.
---

# Python Best Practices — Gen_Ui backend

Adapted from Google's Python Style Guide, PEP 8/257, FastAPI docs, ruff/mypy, and OWASP,
then cut down to what this service actually is. **When this document conflicts with the
existing code, follow the code and say so.**

## 0. This project — what it is and is not

```
backend/
  main.py        # FastAPI app: routes, the OpenAI call, sanitize(), fallbacks
  schemas.py     # THE COMPONENT CATALOG — Pydantic models, both contract directions
  mock_data.py   # the fixed dataset + its plain-text rendering for the prompt
  requirements.txt  .env.example  Dockerfile  .dockerignore
```

Deliberately absent — **do not add these without being asked**:

| Not here | Why |
|---|---|
| Database, SQLAlchemy, Alembic | No persistence. Generated cards live in React state and die on reload. |
| Repository / service layers | Three modules total. A service layer over one OpenAI call is ceremony. |
| Auth, sessions, users | Single-user local experiment. |
| `async def` routes | The OpenAI SDK call is blocking; plain `def` lets FastAPI use its threadpool. **Do not convert routes to `async def` while the client is synchronous** — it would stall the event loop. |
| Streaming responses | The frontend renders one component per request, atomically. |

Runtime is whatever `python:3.12-slim` ships (the Docker image) and 3.14 locally. Use
`X | None`, `list[str]`, `Literal`, and the `|` union operator. Dependencies are
range-pinned in `requirements.txt`; **`openai` is held at `<2`** because the code calls
`client.beta.chat.completions.parse`.

## 1. The two contracts that define this service

Everything else is detail. Get these wrong and nothing works.

### Contract A — `schemas.py` is the component catalog, in both directions

The Pydantic models are simultaneously:

1. the JSON Schema handed to OpenAI as `response_format`, which **constrains what the
   model can emit** (constrained decoding, not instruction-following), and
2. the validator the response is parsed back through before it is serialized.

Consequences, all enforced in review:

- **`Component` is a bare union of `Literal`-tagged models.** Do not add a Pydantic
  `Field(discriminator=...)` — that emits a `discriminator` keyword OpenAI's strict schema
  mode rejects. The `Literal["line_chart"]` tag on each member is what does the work.
- **Every field needs a `description`.** It is prompt text; the model reads it. A field
  named `unit` with no description gets filled with garbage.
- **Avoid `Optional`/defaults inside catalog models.** Strict mode marks every property
  required; a nullable field just makes the model emit `null` and pushes the problem to
  the renderer. Prefer a required field with a documented "0 if unknown" convention.
- **Adding a component type is exactly two edits**: a model here, and a renderer
  registered in the frontend's `RENDERERS` map. If a change needs more, it is wrong.

### Contract B — `/api/generate` never fails

The endpoint returns **HTTP 200 with a valid `Component` on every path** — missing key,
network error, refusal, validation failure, unusable output. The frontend has one happy
path by design; a 500 would leave it with nothing to render.

- Every `except` branch returns a `GenerateResponse` with `fallback=True`, a `text_note`
  component, and `DEFAULT_FOLLOW_UPS`.
- **This is a deliberate deviation** from the usual "log and re-raise at the boundary"
  rule. It is the product requirement. Keep it, and keep the `logger.exception` call —
  swallowing without logging is not the same thing.
- Request-shape errors are the exception: `GenerateRequest` validation still yields 422,
  because a malformed request is a client bug, not a model failure.

## 2. `sanitize()` — shape is not sense

Structured outputs guarantee the *shape*. They cannot guarantee four series instead of
nine, a donut with more than one slice, or a table row whose cell count matches its
columns. `sanitize()` is the layer that enforces meaning:

- **Trim what is trimmable** (`MAX_SERIES`, `MAX_POINTS`, `MAX_SLICES`, `MAX_ROWS`),
  **raise `ValueError` on what is not.** The caller converts that to a fallback.
- Every limit is a module-level `UPPER_SNAKE` constant, and the same numbers appear in
  `SYSTEM_PROMPT`. **Change both together** or the prompt starts lying to the model.
- Keep it pure and synchronous — no I/O, no logging of user content.

## 3. Secrets and error hygiene (the rule most easily broken here)

- **Never put an exception message in an API response.** `GenerateResponse.error` is a
  `Literal` code (`upstream_error`, `missing_api_key`, …), never `str(exc)`. An OpenAI
  `AuthenticationError` string contains a partial API key, and this response is rendered
  verbatim in the browser. Details go to `logger.exception`, which is not user-visible.
- Same rule for `text_note` bodies on fallback paths: generic prose, no `{exc}`.
- `OPENAI_API_KEY` comes from the environment only. **Never** a default, a literal, a test
  fixture, or a comment. `.env` is gitignored; every new variable is documented in
  `backend/.env.example` **and** `compose.yaml` in the same change.
- CORS stays an explicit allow-list from `ALLOWED_ORIGINS`. Never `["*"]`.
- User message text is bounded (`max_length=2000`) and `extra="forbid"` on request models.

## 4. Naming, typing, functions

| Kind | Convention | Here |
|---|---|---|
| Module | `snake_case`, singular | `mock_data.py` |
| Class | `PascalCase` noun | `DonutChart`, `GenerateResponse` |
| Function | `snake_case` verb phrase | `clean_follow_ups()`, `dataset_for_prompt()` |
| Constant | `UPPER_SNAKE`, module top | `MAX_SLICES`, `DEFAULT_FOLLOW_UPS` |
| Private | leading `_` | `_client` |

- **Type-hint every parameter and return**, including `-> None`. Modern syntax only:
  `list[str]`, `str | None`, `A | B`. Not `List`, `Optional`, `Union[...]`.
- `Literal` over magic strings — it is both a type and a prompt constraint here.
- Functions ≤ 30 lines, ≤ 4 parameters. Guard-clause early returns over nesting.
- Never shadow builtins (`id`, `type`, `input`, `list`).

## 5. Errors, logging, imports

- Catch the **narrowest** type. `except Exception` only at the endpoint boundary, and it
  must `logger.exception(...)`.
- No bare `except`, no `except: pass`. Chain with `from exc` when re-raising.
- One module logger: `logger = logging.getLogger("genui")`. **No `print()`.**
- **Lazy `%s` formatting in log calls**, never f-strings: `logger.warning("bad: %s", exc)`.
- Absolute imports, stdlib → third-party → local, one per line. No wildcards.
- Import-time work is confined to `main.py` (`load_dotenv()`, `SYSTEM_PROMPT`). The prompt
  is built once at import **on purpose** — it embeds the whole dataset and should not be
  re-rendered per request. Do not add import-time side effects to `schemas.py` or
  `mock_data.py`; they must stay importable in a test with no environment.

## 6. FastAPI

- **`response_model` on every route.** `/api/dashboard` returns `DashboardResponse`, which
  doubles as validation of the mock fixtures.
- Thin handlers: validate, call, return. Business logic lives in module functions.
- `summary=` on routes so `/docs` is usable.
- Plain `def` handlers — see §0.
- The API is unversioned (`/api/...`, no `/v1`) because nginx and the frontend proxy on
  that prefix and there is exactly one client. If a second client ever appears, version it
  then.

## 7. Testing — **current state: none**

There is no pytest, no config, no coverage. **Do not claim tests were run.** When adding
them:

- `backend/tests/`, `test_<module>.py`, `test_<unit>_<scenario>_<expected>()`.
- **Never call the real OpenAI API in a test.** Stub `ask_model` or the client; assert on
  `sanitize()` and `clean_follow_ups()` directly — they are pure and are where the bugs are.
- Priority order: `sanitize()` edge cases (nine series, one-slice donut, ragged table rows,
  empty series) → every fallback branch of `generate` → `clean_follow_ups` de-duplication →
  `DashboardResponse` accepting the fixtures.
- Assert that **no fallback response body contains an exception string** — that is the
  regression test for the leak fixed in this repo.
- `TestClient` for routes; deterministic, no network, no sleeps.

## 8. Gates — honest baseline

**Nothing is configured.** There is no `pyproject.toml`, no ruff, black, mypy, or pytest.
`requirements.txt` is range-pinned, not a lockfile. Today the only real verification is
running the app and hitting the endpoints.

If you add tooling, this is the target:

```bash
ruff format backend && ruff check --fix backend
mypy backend
pytest backend -q
```

Until then: **run the service and exercise the endpoint you changed, and report the actual
output.** Never claim a gate you did not run.

## 9. AI agent rules

1. **Read `schemas.py` first.** It defines what the model can say and what the frontend can
   draw. Most changes start there.
2. **Keep the catalog and the renderer in sync.** A new component model without a frontend
   renderer produces an "Unsupported component" card.
3. **Keep prompt constants and code constants in sync** (§2).
4. **Never widen what reaches the client.** No exception text, no key material, no stack
   traces in a response body (§3).
5. **Preserve the never-500 contract.** A new failure mode needs a new fallback branch, not
   a raised exception.
6. Type-hint everything; no `Any` without a justifying comment.
7. Never hardcode secrets, model names, or endpoints — environment plus a documented
   default, added to `.env.example` and `compose.yaml` together.
8. Do not add dependencies, layers, async, or a database without asking. The value of this
   codebase is that it is small.
9. **Run what you changed and report real output.** Say plainly when something failed.
10. Keep the diff focused. No drive-by refactors, no commits unless asked.

## 10. Review checklist

**Catalog** — new component has a `Literal` type tag, a description on every field, and a
matching frontend renderer? Discriminator keyword accidentally introduced? Union still
converts to a valid strict schema (`to_strict_json_schema` returns the expected variant
count)?

**Fallback contract** — every new `except` returns a valid `GenerateResponse` with
`fallback=True`? Any path that can now raise out of `generate`?

**Secrets & errors** — any `str(exc)`, `{exc}`, or `repr` of an upstream error in a
response body or `text_note`? Key material in a log line that is also user-visible? New
env var missing from `.env.example` or `compose.yaml`? CORS still an allow-list?

**Sanitize** — limits enforced as constants, mirrored in the prompt? Unusable output
raising rather than shipping a broken card?

**Typing** — full annotations, modern syntax, no `Optional`/`Union[...]`/`Any`?

**Logging** — lazy `%s`, no f-strings, no `print`, `logger.exception` on the boundary
catch, no user content or secrets logged?

**FastAPI** — `response_model` present? handler thin? still plain `def`?

**Docs** — docstring says *why*, not what the signature already says? README updated for
new setup steps or variables?
