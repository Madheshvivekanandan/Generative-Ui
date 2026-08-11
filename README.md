# Generative UI — Financial Dashboard

A minimal round-trip experiment: you type a free-text request, an LLM picks one
UI component from a fixed catalog and fills it with data, and React renders it
live onto the dashboard as a new card.

```
React (Vite)  ──POST /api/generate {message}──▶  FastAPI
                                                   │
                                                   ├─ mock dataset → system prompt
                                                   ├─ OpenAI structured outputs,
                                                   │  schema = the component catalog
                                                   └─ validate + sanitize
              ◀──{ok, explanation, component}──────┘
```

## Running it with Docker

```bash
cp .env.example .env        # put your OpenAI key in it
docker compose up --build
```

Open **http://localhost:3000**. That is the only address you need — nginx serves
the built frontend and proxies `/api` to the backend on the compose network, the
same job the Vite dev proxy does, so the frontend code is identical either way
and CORS never comes up. The backend is also published on `:8000` for `curl` and
`/docs`.

Compose reads the `.env` next to `compose.yaml` and substitutes `OPENAI_API_KEY`
and `OPENAI_MODEL` into the backend's environment. Without it the stack still
comes up and the dashboard renders; only `/api/generate` returns its missing-key
fallback. Change the key and `docker compose up -d` again — no rebuild needed,
it's runtime environment, not baked into the image.

The frontend waits on the backend's `/api/health` healthcheck, so nginx never
starts against a dead upstream.

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
npm install recharts        # the only added dependency
npm run dev                 # http://localhost:5173
```

Vite proxies `/api` to `127.0.0.1:8000`, so nothing in the frontend hardcodes a
backend URL.

## The API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Status, model name, whether a key is configured. |
| `GET /api/dashboard` | The mock dataset the dashboard renders on load. |
| `POST /api/generate` | `{message}` → `{ok, explanation, component, fallback, error}` |

`/api/generate` **always returns HTTP 200.** A missing API key, an upstream
failure, a refusal, or output that fails validation all resolve to a `text_note`
component with `fallback: true`. The frontend therefore has one happy path and
no error branch that can leave it without something to render.

## Component catalog

Defined in `backend/schemas.py`. These Pydantic models *are* the contract: they
generate the JSON Schema that constrains the model's output, and they validate
the response before it is serialized.

| type | when the model picks it | props |
|---|---|---|
| `stat_card` | the answer is one number | `label, value, unit, delta_pct, delta_direction, caption` |
| `line_chart` | change over time | `series[{name, points[{x,y}]}], x_label, y_label, unit` |
| `bar_chart` | comparison across categories | same, plus `stacked` |
| `donut_chart` | composition of a whole | `slices[{label,value}], unit` |
| `data_table` | listing records | `columns[{key,label,align}], rows[][]` |
| `text_note` | nothing else fits; also the fallback | `title, body` |

`unit` is one of `USD | % | count | none` and drives all number formatting on
the client.

## How output is kept safe

Three layers, because each catches something the others cannot:

1. **Structured outputs.** The schema is passed as `response_format`, so the
   model cannot emit a component type that does not exist or omit a required
   prop. Shape is guaranteed at the source.
2. **`sanitize()` in `main.py`.** Shape is not sense. This trims to ≤4 series,
   ≤24 points, ≤6 donut slices, ≤25 table rows, and drops table rows whose cell
   count does not match the column count. If what is left is unrenderable — no
   series, a one-slice donut — it raises and the request falls back.
3. **A defensive renderer.** `ComponentRenderer.jsx` coerces every field it
   reads, dispatches through a whitelist (an unrecognized `type` renders an
   explanatory card rather than throwing), and each card is wrapped in an error
   boundary, so a bad card can only break itself.

The baseline dashboard is itself built from the same six component objects, so
anything that renders on load is something the model can also produce.

## Things deliberately left out

No auth, no database, no persistence, no chat history sent to the model — each
request is independent. Generated cards live in React state and disappear on
reload. The mock data is a module-level constant in `backend/mock_data.py`.

## Notes

- Set `OPENAI_MODEL` in `.env` to use something other than `gpt-4o-mini`; any
  model with structured-outputs support works.
- Chart colors are assigned by fixed slot order and are validated for
  colorblind separation in both light and dark mode, which is why a series never
  changes color when another is added.
