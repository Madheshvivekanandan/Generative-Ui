---
name: react-best-practices
description: React standard for the Gen_Ui frontend — a Vite + React 19 SPA (plain JSX, no TypeScript) that renders a financial dashboard from an LLM-chosen component catalog, using Recharts. Load BEFORE writing, modifying, or reviewing any frontend code in this repo — anything under frontend/src/ (App.jsx, api.js, lib/, components/) or any .jsx/.css file. Covers the renderer contract, defensive rendering, error boundaries, chart/palette rules, state, a11y, performance, and a review checklist.
---

# React Best Practices — Gen_Ui frontend

Correctness and clarity first, then performance. Adapted from React docs, Vercel
Engineering's react-best-practices (MIT), and WCAG, cut down to what this app is.
**When this document conflicts with the existing code, follow the code and say so.**

## 0. This project — the actual stack

```
frontend/src/
  main.jsx                 # entry
  App.jsx                  # layout, dashboard state, baseline component objects
  api.js                   # the ENTIRE backend contract — the only place fetch appears
  index.css                # design tokens + all styling (no CSS-in-JS, no framework)
  lib/format.js            # number formatting + series color slots
  components/
    ComponentRenderer.jsx  # the whitelist dispatch — the heart of the app
    ChatBox.jsx  Card.jsx  ErrorBoundary.jsx  ChartTooltip.jsx
```

- **Vite + React 19, plain JSX. There is no TypeScript**, no `tsc`, no type-checking gate.
- **Recharts** is the only runtime dependency beyond React.
- **Plain CSS with custom properties** in `index.css`. No MUI, no Tailwind, no styled-components.
- No router, no state library, no data-fetching library.

**Rules that do not apply here — never suggest them:** RSC / `"use client"`, anything
`next/*`, SSR/hydration, Refine or TanStack Query hooks, MUI barrel-import rules,
react-hook-form, `useSearchParams` (there is no router).

## 1. The renderer contract

The backend sends `{type, ...props}` chosen from a fixed catalog. `ComponentRenderer.jsx`
turns that into a card. This is the one thing to understand before editing anything.

- **Dispatch through the `RENDERERS` whitelist**, checked with
  `Object.prototype.hasOwnProperty`. Never `RENDERERS[component.type]` bare — an unknown
  or prototype-polluting `type` must render an explanatory card, not throw.
- **Treat every field as untrusted.** The payload comes from an LLM. Read it through the
  `str()` / `num()` / `arr()` coercers at the top of the file; never index into
  `component.series[0].points[0]` directly. A `null`, a string where a number belongs, or
  a missing array is expected input, not an exceptional case.
- **A renderer returns `<EmptyState/>` rather than throwing** when there is nothing to
  draw. Empty is a normal outcome.
- **Adding a component type is exactly two edits**: a Pydantic model in `backend/schemas.py`
  and a renderer registered in `RENDERERS`. Wide types also go in `WIDE_TYPES`.
- **The baseline dashboard uses the same catalog.** `baselineComponents()` in `App.jsx`
  builds the load-time cards as plain component objects through the same renderer. Never
  add a privileged path for "real" cards — if it renders on load, the model can produce it.

## 2. Error handling — the app must not be able to crash

This is the product requirement, not a nicety. Five layers, each catching what the others
cannot; **never remove one because another looks sufficient.**

| Layer | Catches |
|---|---|
| Backend structured outputs | invented component types, missing props |
| Backend `sanitize()` | valid shape, unusable content |
| `api.js` try/catch | network down, non-JSON, non-2xx |
| Coercers + whitelist in `ComponentRenderer` | wrong types, nulls, unknown `type` |
| `<ErrorBoundary>` per card | any render-time throw |

- **Every card is individually wrapped in `<ErrorBoundary>`.** One bad card must never
  blank the dashboard.
- **`api.js` resolves, it does not throw**, for `generateComponent` — it returns a
  synthetic `text_note` on network failure so callers have one shape to handle.
- **Never render a raw error string to the user.** Error boundaries and fallback cards show
  generic prose; the detail goes to `console.error`. Backend exception text and component
  stacks are internal detail.
- Show **loading, empty, and error** as three distinct states. Never conflate empty with error.
- Boundaries catch render errors only — never async or event-handler errors. Those need
  explicit try/catch.

## 3. State

- **Local `useState` in the nearest owner** is correct here. There is no server-state
  library and no router, so a `useEffect` + `fetch` + `setState` for the dashboard payload
  is the right call, not a smell — but keep it to `api.js` calls in `App.jsx`, and keep the
  `cancelled` flag so a late response cannot set state after unmount.
- **Derive, never duplicate.** `baseline` is a `useMemo` over the fetched dataset, not a
  second piece of state. No `useEffect` that only computes something render could.
- **Functional updates** (`setMessages(prev => …)`) so callbacks stay stable.
- IDs come from a `useRef` counter, never array index or `Date.now()`.
- Name state for its domain: `dashboard`, `generated`, `messages`. **Never `data`, `item`,
  `tmp`, `res`, `x`.**

## 4. Components & naming

| Unit | Limit |
|---|---|
| Component file | ≤ 250 lines |
| Component body | ≤ 120 lines |
| JSX nesting | ≤ 4 |
| Props | ≤ 8 |

`ComponentRenderer.jsx` is near the file limit by design — it holds all six renderers plus
dispatch, which keeps the catalog readable in one place. **If it grows past ~300 lines,
split the renderers into `components/renderers/` rather than trimming the coercers.**

- **Never define a component inside a component** — it remounts and loses state every
  parent render. `Suggestions` in `ChatBox.jsx` is module-scope for this reason.
- `handle*` for internal handlers, `on*` for props. `is/has/can/should` for booleans.
- `UPPER_SNAKE` module constants — `MAX_SERIES`, `OPENERS`, `CHART_HEIGHT`. No inline magic numbers.
- Ternaries for conditional render, never `&&` with a possibly-numeric left side
  (`{count && <X/>}` renders a literal `0`).

## 5. Charts (Recharts) — the palette is validated, don't improvise

The color system was validated for colorblind separation against both surfaces. Treat it
as fixed.

- **Series colors come from `seriesColor(index)` in `lib/format.js`**, assigned by slot in
  fixed order. Never hardcode a hex in a component, and never let color follow rank —
  filtering a series out must not repaint the survivors.
- **Cap at 4 series / 6 donut slices.** These mirror the backend's `sanitize()` limits;
  change both together.
- **One y-axis. Never a dual-axis chart.** Two measures of different scale → two cards.
- Colors are CSS custom properties (`var(--series-1)`) so light/dark swap in one place.
  Both modes are defined in `index.css` — dark is a selected set of steps, not a flip.
- Every chart ships a hover tooltip (`ChartTooltip`) and a legend when there are ≥ 2 series
  (one series needs none — the title names it).
- Thin marks: 2px lines, `dot={false}` with an `activeDot` on hover, 4px bar corner radius,
  a 2px surface-colored gap between stacked fills.
- Numbers go through `formatCompact` (axes) / `formatFull` (tooltips, stat values). Never
  hand-concatenate a currency symbol.
- Text wears text tokens (`--text-primary/secondary/muted`), never a series color.

## 6. Accessibility

- Icon-only controls need an accessible name — the card dismiss button uses `aria-label`.
- The chat input has an `aria-label`; keep it, there is no visible `<label>`.
- Announce async results: the "Thinking…" row and new-card arrival should be reachable by
  a screen reader (`role="status"` is the cheapest fix — **currently missing, worth adding**).
- Semantic elements first: `<main>`, `<aside>`, `<section>`, `<table>`, real `<button>`s.
- Never encode meaning by color alone — the KPI delta pairs its color with an arrow glyph.
- Keep focus outlines. Body text contrast ≥ 4.5:1.

## 7. Performance

Correctness first; only optimize with a measurement. Relevant here:

- **`recharts` is imported as a barrel and the bundle is ~609 kB (178 kB gzipped), one
  chunk, no code splitting.** This is the known baseline. If it becomes a problem, the fix
  is `React.lazy` + `<Suspense>` around the chart renderers, not shaving elsewhere.
- Stable, data-derived `key`s. Array index is acceptable *only* for the table body rows,
  which are never reordered or filtered — anywhere else it is a bug.
- No `await` inside a loop; independent requests go in `Promise.all`.
- `useMemo`/`useCallback` where they prevent real work (`baseline`, `send`, `dismiss`) —
  not on primitive comparisons.
- Only `.dashboard` and `.chat-log` scroll; `.shell` is `overflow: hidden`. Keep it that
  way or the fixed layout breaks.

## 8. Gates — honest baseline

```bash
npm run lint       # oxlint — configless, currently CLEAN (zero findings)
npm run build      # vite build — currently passes, ~609 kB / 178 kB gzipped
npm run dev        # then click through the app
```

- **The linter is `oxlint`, not ESLint.** There is no `eslint.config.js` and none is
  needed — oxlint runs without configuration. `npm run lint` is a real gate and it is
  currently green: **never leave it with a new finding.**
- **There is no TypeScript and no `npm run typecheck`.**
- **There is no test framework.** If adding one: Vitest + React Testing Library + MSW.
  Priority order — `ComponentRenderer` against malformed payloads (the coercers are the
  highest-value thing to test), `api.js` network-failure path, `ErrorBoundary` containment,
  `formatCompact`/`formatFull` edges.

`npm run build` succeeding means it compiled, **not** that it works. Run the app.

## 9. AI agent rules

1. **Read `ComponentRenderer.jsx` first** — it defines what can be drawn.
2. **Keep the catalog in sync with `backend/schemas.py`.** Two edits, always.
3. **Never trust the payload.** New field reads go through the coercers.
4. **Never remove an error-handling layer** (§2), and never render a raw error to a user.
5. **Never hardcode a chart color or bypass `seriesColor()`.**
6. Never mirror one piece of state into another; derive during render.
7. No new dependency without asking — the dependency list is deliberately two entries long.
8. **Run `npm run build` and actually load the app; report real output.** Do not claim a
   lint, typecheck, or test that does not exist here.
9. Keep the diff focused. No drive-by refactors, no reformatting untouched files, no
   commits unless asked.
10. Plain JSX. Do not introduce `.tsx` files piecemeal — converting the app to TypeScript
    is a whole-project decision, not a side effect of another change.

## 10. Review checklist

**Renderer** — whitelist dispatch intact (`hasOwnProperty`, not a bare index)? new field
reads coerced? renderer returns `<EmptyState/>` instead of throwing on empty? new type
registered in both `RENDERERS` and, if wide, `WIDE_TYPES`?

**Errors** — every card still inside an `<ErrorBoundary>`? `api.js` still resolving rather
than throwing? any raw error message, stack, or backend exception text rendered to the
user? empty `catch`? loading/empty/error all present?

**State** — server payload mirrored into a second state? `useEffect` computing what render
could? stale-response guard present on the fetch? identifier named `data`/`tmp`/`item`?

**Charts** — hardcoded hex instead of `seriesColor()`? more than 4 series or 6 slices?
dual axis? legend missing with ≥ 2 series? limits still matching the backend's?

**Components** — component defined inside a component? file over 250 lines? `&&` with a
numeric left side? array index as `key` outside the static table body?

**A11y** — icon-only button without a name? input without a label? status by color alone?
focus outline removed?

**Gates** — `npm run build` actually run and reported? no claim of lint/typecheck/tests,
which do not exist in this project?
