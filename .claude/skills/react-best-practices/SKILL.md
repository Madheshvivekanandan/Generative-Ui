---
name: react-best-practices
description: React standard for the Gen_Ui frontend — a Vite + React 19 SPA (plain JSX, no TypeScript) that renders a financial dashboard from A2UI v0.9 messages via @a2ui/react, with an LLM-constrained component catalog and Recharts views. Load BEFORE writing, modifying, or reviewing any frontend code in this repo — anything under frontend/src/ (App.jsx, a2ui/, components/, lib/) or any .jsx/.css file. Covers the A2UI catalog contract, defensive rendering, error boundaries, the single-canvas model, chart/palette rules, state, a11y, performance, and a review checklist.
---

# React Best Practices — Gen_Ui frontend

Correctness and clarity first, then performance. Adapted from React docs, Vercel
Engineering's react-best-practices (MIT), and WCAG, cut down to what this app is.
**When this document conflicts with the existing code, follow the code and say so.**

## 0. This project — the actual stack

```
frontend/src/
  main.jsx                 # entry
  App.jsx                  # the MessageProcessor wiring, canvas state, chat state
  index.css                # design tokens + all styling (no CSS-in-JS, no framework)
  a2ui/
    transport.js           # hand-rolled SSE reader (fetch + getReader; EventSource can't POST)
    catalog.jsx            # THE CATALOG — Zod-described components the renderer may draw
    coerce.js              # str/num/arr readers + toChartRows; nothing here throws
    views.jsx              # the six Recharts views; know nothing about A2UI
  components/
    ChatBox.jsx  ErrorBoundary.jsx  ChartTooltip.jsx
  lib/format.js            # number formatting + series color slots
```

- **Vite + React 19, plain JSX. There is no TypeScript**, no `tsc`, no type-checking gate.
- Runtime deps: `react`, `react-dom`, `@a2ui/react`, `@a2ui/web_core`, `recharts`, `zod`.
  (`@a2ui/markdown-it` is imported in App.jsx but supplied transitively by `@a2ui/react`.)
- **npm version ≠ protocol version:** the packages are 0.10.x but every import is from
  `/v0_9` subpaths — the 0.10.x package line implements protocol v0.9.
- **`zod` must stay on v3.** The binder classifies props by reading Zod 3 internals;
  Zod 4 renamed them and the failure is silent (`[object Object]` everywhere).
- **Plain CSS with custom properties** in `index.css`. No MUI, no Tailwind.
- No router, no state library, no data-fetching library.

**Rules that do not apply here — never suggest them:** RSC / `"use client"`, anything
`next/*`, SSR/hydration, TanStack Query, MUI barrel-import rules, react-hook-form,
`useSearchParams` (there is no router).

## 1. The A2UI contract

The backend streams A2UI v0.9 messages; `@a2ui/react` renders them against the catalog.
This is the one thing to understand before editing anything.

- **`financeCatalog` in `a2ui/catalog.jsx` is the security boundary.** The renderer
  refuses any component name not in it — enforced by the library, not by a check someone
  must remember to write. A2UI's basic components are listed one by one instead of
  spreading `basicCatalog`, so the file is an honest inventory of what an agent can put
  on screen.
- **Declare twice:** each custom component is a Zod schema (its public API — all props
  `.optional()`, because the data model can be mid-stream when a component first renders)
  plus an implementation via `createComponentImplementation` that receives already-
  resolved values. Views never see a `{path: ...}` binding.
- **`Card` replaces A2UI's own for exactly one reason: the error boundary.** A card is
  the unit of failure; the boundary must live at the card, so one malformed chart can
  break only its own card. Never move the boundary to the surface.
- **One canvas.** Everything renders into the fixed surface id `dashboard`
  (`CANVAS_SURFACE`, matching `backend/main.py`). `send()` clears it with a
  `deleteSurface` *through the processor* before each turn streams, so the answer
  re-forms in place. Never splice React state around the processor — protocol state and
  app state must not drift.
- **`processor.model.surfacesMap` is externally owned and mutated in place.** React
  cannot observe it; the app re-snapshots (`new Map(...)`) on `onSurfaceCreated` /
  `onSurfaceDeleted`. Keep that pattern.
- **The action handler is guarded while a turn is streaming** (`busyRef`) — with a single
  canvas, a mid-stream button press would put two writers on one surface.
- **Two SSE channels by `event:` name:** `a2ui` frames go straight to
  `processor.processMessages`; `meta` frames drive the chat log and are NOT A2UI. A
  malformed frame is dropped, never fatal — the authoritative pass resends state.
- **Adding a component type is exactly three edits**: a Pydantic model in
  `backend/schemas.py`, a `_VIEW` row in `backend/a2ui.py`, and a component registered in
  `catalog.jsx`. If a change needs more, it is wrong.
- Markdown is opt-in via `MarkdownContext` (sanitized through DOMPurify). Never render
  agent text through `dangerouslySetInnerHTML`.

## 2. Error handling — the app must not be able to crash

This is the product requirement. Layers, each catching what the others cannot;
**never remove one because another looks sufficient:**

| Layer | Catches |
|---|---|
| Backend structured outputs + `sanitize()` | invented types, missing props, unusable content |
| `transport.js` | network death, malformed frames, non-2xx (resolves via `onError`, never rejects) |
| Catalog whitelist (`@a2ui/react`) | unknown component names |
| Coercers in `coerce.js` | wrong types, nulls, missing arrays |
| `<ErrorBoundary>` per card (inside `Card`) | any render-time throw |

- **Treat every field as untrusted.** Payloads come from an LLM. Read through
  `str()` / `num()` / `arr()`; never index into `series[0].points[0]` directly. A `null`
  or a string-where-a-number-belongs is expected input, not an exceptional case.
- **A view returns `<EmptyState/>` rather than throwing** when there is nothing to draw.
- **Never render a raw error string to the user.** Boundaries and fallbacks show generic
  prose; detail goes to `console.error`.
- A dead transport restores the baseline into the canvas rather than leaving it blank.
- Boundaries catch render errors only — async/event-handler errors need try/catch.

## 3. State

- **Local `useState` in the nearest owner** is correct here. Keep fetches in
  `a2ui/transport.js`, called from `App.jsx`, with a `cancelled` flag so a late response
  cannot set state after unmount.
- **Molecule data is NOT React state** — it lives in the processor's data model. React
  state holds only chrome: messages, busy, canvasPrompt, the surface snapshot.
- **Derive, never duplicate.** `canvas` is a `useMemo` over the snapshot, not a second
  piece of state.
- **Functional updates** (`setMessages(prev => …)`) so callbacks stay stable.
- The processor is created once in `useMemo`; `sendRef`/`busyRef` break the circular
  dependency with `send` without rebuilding it (a rebuild discards every surface).
- IDs come from a `useRef` counter, never array index or `Date.now()`.
- Name state for its domain: `canvasPrompt`, `messages`, `busy`. **Never `data`, `tmp`.**

## 4. Components & naming

| Unit | Limit |
|---|---|
| Component file | ≤ 250 lines |
| Component body | ≤ 120 lines |
| JSX nesting | ≤ 4 |
| Props | ≤ 8 |

- **Never define a component inside a component** — it remounts and loses state every
  parent render. `Suggestions` in `ChatBox.jsx` is module-scope for this reason.
- `handle*` for internal handlers, `on*` for props. `is/has/can/should` for booleans.
- `UPPER_SNAKE` module constants — `CHART_HEIGHT`, `MAX_SLICES`, `CANVAS_SURFACE`.
- Ternaries for conditional render, never `&&` with a possibly-numeric left side.

## 5. Charts (Recharts) — the palette is validated, don't improvise

The color system was validated for colorblind separation against both surfaces. Treat it
as fixed.

- **Series colors come from `seriesColor(index)` in `lib/format.js`**, assigned by slot
  in fixed order. Never hardcode a hex; never let color follow rank — filtering a series
  out must not repaint the survivors.
- **Cap at 4 series / 6 donut slices** — mirrors the backend's `sanitize()`; change both
  together (`toChartRows` and the donut view carry the frontend halves).
- **One y-axis. Never a dual-axis chart.** Two measures of different scale → two cards.
- Recessive chrome: no axis or tick lines; dashed horizontal gridlines only
  (`var(--grid)`); muted 11px ticks. Gradient area fill under **single-series** lines
  only (unique ids via `useId` — several charts can share the canvas).
- Legend only for ≥ 2 series (dot icons); one series is named by the card title.
- Every chart ships the hover tooltip (`ChartTooltip`); numbers go through
  `formatCompact` (axes) / `formatFull` (tooltips, stat values).
- Colors are CSS custom properties; both themes are separately chosen steps, not a flip.
- Text wears text tokens, never a series color.

## 6. Accessibility & motion

- Icon-only controls need an accessible name — the canvas reset button uses `aria-label`.
- The chat input keeps its `aria-label`; there is no visible `<label>`.
- Async results are announced via the `role="status"` live region in App.jsx — keep it.
- Semantic elements first: `<main>`, `<aside>`, `<section>`, `<table>`, real `<button>`s.
- Never encode meaning by color alone — deltas pair color with a glyph and sign.
- Keep focus states: the global `:focus-visible` outline and the chat form's ring.
- **Motion is transform/opacity only, under 300ms, strong ease-out** (`--ease-out`), and
  every animation has a `prefers-reduced-motion` fallback. The canvas entrance
  (`turn-enter`), skeleton sweep, and busy shimmer all follow this — new motion must too.

## 7. Performance

Correctness first; only optimize with a measurement. Relevant here:

- **The bundle is one ~906 kB chunk (~280 kB gzipped)** — Recharts plus the A2UI
  renderer. This is the known baseline. If it becomes a problem, the fix is `React.lazy`
  + `<Suspense>` around the chart views, not shaving elsewhere.
- Stable, data-derived `key`s. Array index is acceptable *only* for the static table
  body rows — anywhere else it is a bug.
- `useMemo`/`useCallback` where they prevent real work (the processor, `send`, `canvas`).
- Only `.dashboard` and `.chat-log` scroll; `.shell` is `overflow: hidden`. Keep it that
  way or the fixed layout breaks.

## 8. Gates — honest baseline

```bash
npm run lint       # oxlint, configured in .oxlintrc.json — currently CLEAN
npm run build      # vite build — passes; ~906 kB / ~280 kB gzipped, one chunk
npm run dev        # then actually click through the app
```

- **The linter is `oxlint`, not ESLint**, configured by `.oxlintrc.json`. `npm run lint`
  is a real gate and it is currently green: **never leave it with a new finding.**
- **There is no TypeScript and no test framework.** If adding one: Vitest + React Testing
  Library. Priority order — the coercers against malformed payloads, `transport.js`
  frame-splitting across chunk boundaries, `ErrorBoundary` containment, format edges.
- `npm run build` succeeding means it compiled, **not** that it works. Run the app.

## 9. AI agent rules

1. **Read `a2ui/catalog.jsx` first** — it defines what can be drawn — then `App.jsx` for
   the processor wiring and the single-canvas model.
2. **Keep the three-edit rule:** backend schema + `_VIEW` row + catalog component, always
   in step.
3. **Never trust the payload.** New field reads go through the coercers; new catalog
   props are `.optional()`.
4. **Never remove an error-handling layer** (§2), never render a raw error, never move
   the boundary off the card.
5. **Never bypass the protocol:** canvas clears go through `processor.processMessages`,
   not React state surgery.
6. **Never hardcode a chart color or bypass `seriesColor()`.**
7. No new dependency without asking, and never bump `zod` past v3 (§0).
8. New animation follows §6 (transform/opacity, <300ms, reduced-motion fallback).
9. **Run `npm run lint` and `npm run build`, load the app, and report real output.** Do
   not claim a typecheck or tests that do not exist here.
10. Plain JSX; converting to TypeScript is a whole-project decision, not a side effect.
    Keep the diff focused; no commits unless asked.

## 10. Review checklist

**Contract** — new component in the catalog with Zod props `.optional()`? backend
`_VIEW` + schema edited together? boundary still inside `Card`? canvas still cleared via
`deleteSurface` before a turn? busy guard intact on the action handler?

**Errors** — every card still inside the boundary? `transport.js` still resolving (never
rejecting)? any raw error text rendered? loading/empty/error all distinct?

**State** — processor data mirrored into React state? `useEffect` computing what render
could? stale-response guard present? processor rebuilt accidentally (deps on the
`useMemo`)?

**Charts** — hardcoded hex? more than 4 series / 6 slices? dual axis? legend missing
with ≥ 2 series? gradient fill on a multi-series chart? `useId` missing on a new
gradient?

**Components** — component defined inside a component? file over 250 lines? `&&` with a
numeric left side? array index as `key` outside the static table body?

**A11y & motion** — icon button without a name? status by color alone? focus ring
removed? animation without a reduced-motion fallback, or animating layout properties?

**Gates** — lint and build actually run and reported? no claim of tests, which do not
exist in this package?
