# Generative UI — A2UI Financial Dashboard

You type a request in plain English. An agent composes a small layout from a
fixed component catalog, and it streams into the page as it is composed — as
[A2UI](https://a2ui.org) messages, rendered by `@a2ui/react`. The cards it
produces carry their own buttons, and pressing one sends an action back to the
agent, which answers with new UI.

```
Browser                                    FastAPI
  │  POST /api/generate {session_id, message}
  │─────────────────────────────────────────▶│
  │                                          ├─ replay conversation history
  │                                          ├─ OpenAI structured outputs
  │                                          │    schema = the block catalog
  │◀── SSE: createSurface ────────────────────┤
  │◀── SSE: updateDataModel /blocks/0 ────────┤  optimistic: as each block
  │◀── SSE: updateComponents ─────────────────┤  finishes streaming
  │◀── SSE: updateDataModel / ────────────────┤  authoritative: validated
  │◀── SSE: updateComponents ─────────────────┤  and sanitised
  │                                          │
  │  POST /api/action {name, context}         │  user pressed a generated
  │─────────────────────────────────────────▶│  button — same loop again
```

## Why A2UI

The agent never sends code or markup. It sends a declarative description that
names components from a catalog the *client* defines, so the worst a
misbehaving model can do is ask for a component that does not exist — which the
renderer refuses. That whitelist is the security boundary, and it is enforced by
the renderer rather than by a check somebody has to remember to write.

Adopting the real protocol also means streaming, data binding and the
action round-trip are not features we built; they are what the protocol *is*.

**Version:** A2UI **v0.9**, not the v1.0 candidate. v0.9 is the current
production spec and the only version `@a2ui/react` implements natively today.
The differences that matter here are that v0.9's `createSurface` carries no
inline `components` or `dataModel` (they arrive as separate update messages) and
that there is no client-to-server `actionResponse` yet — our action handler
answers with a fresh surface instead.

## Two contracts, on purpose

There are two schemas in this project and it is worth being clear about why.

| | Where | What it is |
|---|---|---|
| **Block catalog** | `backend/schemas.py` | Pydantic models that constrain what the LLM may emit |
| **A2UI catalog** | `frontend/src/a2ui/catalog.jsx` | Zod-described components the renderer will draw |

The agent plans in typed *blocks*; `backend/a2ui.py` compiles those blocks into
A2UI messages. The wire format and the client are genuine A2UI — only the
agent's internal planning step is typed.

This is a deliberate deviation. A2UI messages are a flat, loosely-typed
component stream: ideal for a renderer, hostile to schema-constrained
generation. Compiling from a typed plan keeps OpenAI structured outputs in the
loop, which means the model **cannot** emit a component type that does not
exist or omit a required prop. Handing the model raw A2UI would trade that
guarantee for prompting and hope.

The cost is that the agent composes from the layouts our compiler knows how to
build (cards, a tile row, actions) rather than arbitrary A2UI trees. For a
dashboard that is the right trade; for a general-purpose agent surface it would
not be.

## Running it with Docker

```bash
cp .env.example .env        # put your OpenAI key in it
docker compose up --build
```

Open **http://localhost:3000**. nginx serves the built frontend and proxies
`/api` to the backend, the same job the Vite dev proxy does, so the frontend
code is identical either way and CORS never comes up. The backend is also
published on `:8000` for `curl` and `/docs`.

Without a key the stack still comes up and the baseline dashboard renders; only
generation returns its missing-key fallback.

> `proxy_buffering off` in `frontend/nginx.conf` is load-bearing. With buffering
> on, nginx holds every SSE frame until the turn ends, the progressive render
> disappears, and everything still *works* — which is what makes it easy to
> break without noticing.

## Running it locally, without Docker

**Backend** (needs an OpenAI key):

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your key in it
uvicorn main:app --reload --port 8000
```

**Frontend**, in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## The API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Status, model, whether a key is set, protocol version, catalog id |
| `GET /api/dashboard/a2ui` | The baseline dashboard as a batch of A2UI messages |
| `GET /api/dashboard` | The raw mock dataset — for `curl` and `/docs` only |
| `POST /api/generate` | `{session_id, message}` → an SSE stream of A2UI messages |
| `POST /api/action` | An A2UI action from the renderer → another stream |

The stream carries two channels, distinguished by the SSE `event:` name:

- `a2ui` — a real A2UI message, handed straight to the `MessageProcessor`
- `meta` — this app's own chat metadata (explanation, follow-up chips). **Not
  part of A2UI**; it drives the chat log, not the dashboard.
- `open` / `done` — the turn's surface id, and its end.

`/api/generate` **never returns an error status.** A missing key, an upstream
failure, a refusal, or output that fails validation all resolve to a `text_note`
block with `fallback: true`. The renderer therefore has one happy path and no
error branch that can leave it with nothing to draw.

## The block catalog

Defined in `backend/schemas.py`. A turn returns **one to four** blocks, laid out
top to bottom, so "how did Q3 go" can answer with a KPI row above a chart.

| type | when the model picks it | props |
|---|---|---|
| `stat_card` | the answer is one number | `title, value, unit, delta_pct, delta_direction, caption` |
| `line_chart` | change over time | `series[{name, points[{x,y}]}], x_label, y_label, unit` |
| `bar_chart` | comparison across categories | same, plus `stacked` |
| `donut_chart` | composition of a whole | `slices[{label,value}], unit` |
| `data_table` | listing records | `columns[{key,label,align}], rows[][]` |
| `text_note` | nothing else fits; also the fallback | `title, body` |

Every block also carries `actions[{label, prompt}]` — up to two buttons rendered
on the card. `label` is what the user sees; `prompt` is the request sent back
when it is pressed. One action name (`refine`) covers every button the model can
invent, because the interesting part travels in the action context.

`unit` is one of `USD | % | count | none` and drives all number formatting.

Consecutive `stat_card` blocks are packed into a Row and given A2UI's `weight`
so they share the width; everything else is full width.

## How output is kept safe

Five layers, because each catches something the others cannot. **Removing one
because another looks sufficient is how this breaks.**

1. **Structured outputs.** The block schema is the `response_format`, so the
   model cannot invent a type or omit a required prop. Shape is guaranteed at
   the source.
2. **`sanitize()` in `a2ui.py`.** Shape is not sense. Trims to ≤4 series, ≤24
   points, ≤6 slices, ≤25 rows, drops table rows whose cell count does not match
   the column count, and raises on what is left unrenderable. One bad block is
   dropped; the rest of the turn survives.
3. **The A2UI catalog whitelist.** The renderer will only draw components in
   `financeCatalog`. An unknown component name is refused, not guessed at.
4. **Coercers in `frontend/src/a2ui/coerce.js`.** Every field a view reads goes
   through `str`/`num`/`arr`. A `null`, or a string where a number belongs, is
   expected input; a view returns an empty state rather than throwing.
5. **An error boundary per card.** Our catalog replaces A2UI's `Card` for this
   one reason: the boundary has to sit at the card, so a bad chart can only
   break its own card and not the whole answer.

The baseline dashboard is built from the same blocks and compiled by the same
module (`backend/baseline.py`), so anything on screen at load is something the
agent could also have produced — and a compiler bug shows up before you type
anything.

## Conversation memory

`backend/session.py` keeps a rolling 12-turn transcript per session, replayed
ahead of the current message, which is what makes "now compare that to
expenses" resolve. The transcript records what was *rendered* alongside the
explanation, so "that chart" has something to point at.

In-memory and process-local: a restart is a fresh conversation. Swapping in
Redis means replacing that one module.

## Things deliberately left out

No auth, no database, no persistence. Generated surfaces live in the renderer's
state and disappear on reload. The dataset is a module-level constant in
`backend/mock_data.py`. No observability beyond log lines — no traces, no
token accounting, no record of which prompts produced which components.

## Notes

- Set `OPENAI_MODEL` in `.env` to use something other than `gpt-4o-mini`; any
  model with structured-outputs support works.
- Chart colours are assigned by fixed slot order and validated for colourblind
  separation in both light and dark mode, which is why a series never changes
  colour when another is added.
- A2UI's basic catalog components are themed by remapping the `--a2ui-*` custom
  properties onto this project's design tokens in `index.css`. No A2UI component
  is restyled by selector, so a renderer upgrade should not break the look.
- Frontend bundle is ~906 kB (279 kB gzipped) in one chunk — up from ~775 kB
  before A2UI. If that matters, the fix is `React.lazy` around the chart views.
