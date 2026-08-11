---
name: react-best-practices
description: React/TypeScript engineering standard for Vite + React 18 SPAs built with Refine, MUI, react-hook-form, and react-router v6. Load BEFORE writing, modifying, or reviewing any React code in such an app — anything under src/ (pages/, components/, providers/, hooks) or any .tsx/.ts component, hook, data fetch, form, MUI DataGrid, or theme change. Covers component architecture, naming, state management, TypeScript, error handling, forms, testing, security, accessibility, performance (waterfalls, bundle size, re-renders), tooling gates, and a review checklist.
license: MIT
metadata:
  perf-rules-adapted-from: vercel-labs/agent-skills — skills/react-best-practices (MIT, v1.0.0)
  stack: vite + react 18 + typescript + refine + mui
---

# React Best Practices (Vite + Refine + MUI SPA)

Correctness and clarity first, then performance. Performance rule IDs
(`async-parallel`, `rerender-memo`, …) come from **Vercel Engineering's
react-best-practices** (MIT) and stay traceable upstream:
`https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices/rules`

## 0. Target Stack & What Does Not Apply

This skill targets a **Vite + React 18 SPA** (TypeScript 5.4, `strict: true`), not Next.js:

```
src/
  pages/<feature>/          # route screens
    components/             #   feature-local components
  components/common/, components/layout/
  providers/                # Refine data/auth providers (dataProvider.ts, authProvider)
  interfaces/               # shared domain types
  config/, theme/, utils/
```

- Stack: `@refinedev/core` + `@refinedev/mui`, MUI 5 (`@mui/material`, `@mui/x-data-grid`,
  `@mui/x-date-pickers`), `react-hook-form`, `react-router-dom` v6, `axios`, `dayjs`.
- Import alias `@/*` → `src/*` is configured — prefer it over deep `../../..` chains.
- Money is **INR**. Use a shared formatter (`Intl.NumberFormat("en-IN", {currency:"INR"})`);
  never hand-concatenate a symbol, never float-accumulate currency.

**Upstream rules that DO NOT apply here — never suggest them:**

| Not applicable | Why |
|---|---|
| RSC / Server Components, `"use client"` | No RSC; everything is a client component. |
| `next/dynamic`, `next/image`, `next/font`, `next/script` | No Next.js. Use `React.lazy` + `<Suspense>`. |
| Server actions, `server-auth-actions`, `after()` | No server runtime; this is a pure client SPA calling a separate backend API. |
| `server-cache-react` (`React.cache()`), RSC prop serialization | Server-only APIs. |
| SSR hydration rules (`rendering-hydration-*`) | SPA — no SSR/hydration step. |
| SWR (`client-swr-dedup`) | Refine wraps TanStack Query, which already dedupes/caches. Don't add SWR. |

## 1. Philosophy

- **Readability over cleverness**; the next reader is the maintainer.
- **Correctness and clarity before optimization.** Only optimize with a measurement.
- **Colocate, then extract.** Keep code near its use; extract when a second caller appears.
- **One responsibility per component.** Data-shaping, side effects and markup want separating.
- **Make invalid states unrepresentable** with types, rather than defending against them at runtime.
- **Never leave the user staring at a blank screen** — every async path has loading and error states.

## 2. Component Architecture & Naming

**Size limits (enforced in review).** Extract past these:

| Unit | Limit |
|---|---|
| Component file | **≤ 250 lines** |
| Component function body | ≤ 120 lines / ≤ 5 hooks doing unrelated work |
| JSX nesting depth | ≤ 4 |
| Props on one component | ≤ 8 (past that, group into an object or split) |

> This codebase currently violates this: `ManagerSettingsPage.tsx` (846 lines),
> `EnquiryLineItemsCard.tsx` (532), `POValidateCard.tsx` (470), `InvoiceReviewPanel.tsx` (453),
> `DispatchTrackingCard.tsx` (424). **Don't grow them further** — when editing one, extract the
> part you touch into `pages/<feature>/components/`. Don't refactor wholesale unless asked.

- **Split by responsibility:** a page composes; child components render sections; **custom hooks
  own data + logic**. If a component both fetches/derives and renders 200 lines of JSX, the
  fetch/derive half becomes `use<Feature>()` in the feature folder.
- **New feature** → `pages/<feature>/` with a `<Feature>Page.tsx` + `components/`.
  Reusable across features → `components/common/`. Shared types → `interfaces/`.
- **Composition over prop-drilling and over configuration flags.** Prefer `children`/slots to a
  `variant`-plus-ten-booleans API. Past 2 levels of drilling, use context or restructure.
- **No inline component definitions** — see `rerender-no-inline-components` (§8).

**Naming**

| Kind | Convention | Good | Bad |
|---|---|---|---|
| Component file + fn | `PascalCase`, matching | `CreditProfileCard.tsx` | `card2.tsx`, `index.tsx` everywhere |
| Hook | `use` + noun/verb | `useTicketFilters()` | `ticketStuff()` |
| Event handler (internal) | `handle*` | `handleSubmit` | `onSubmitClick2`, `doIt` |
| Event prop (external) | `on*` | `onApprove` | `approveCb` |
| Boolean prop/state | `is/has/can/should*` | `isCreditBlocked` | `flag`, `status2` |
| Constant | `UPPER_SNAKE` module scope | `MAX_LINE_ITEMS` | inline `50` |
| Type / interface | `PascalCase`, no `I` prefix | `Ticket`, `CreditProfile` | `ITicket`, `TicketType2` |
| Units in the name | always | `timeoutMs`, `amountInr` | `timeout`, `amount` |

- Name for the **domain**, not the mechanism: `unpaidInvoices`, not `data2`/`filteredList`.
- Never `data`, `item`, `tmp`, `res`, `x` as a meaningful identifier.

## 3. State Management — Pick the Right Location

Choosing wrong here causes most React bugs. In priority order:

1. **Server state → Refine hooks** (`useList`, `useOne`, `useCustom`, `useUpdate`).
   Never mirror fetched data into `useState`; that's a stale-copy bug. Never hand-roll
   `useEffect` + `axios` + `setState` — you lose dedup, caching, and cancellation.
2. **URL state → `useSearchParams`** (react-router v6). **Filters, pagination, sort, active tab,
   and selected-row id belong in the URL**, not `useState`. Makes views shareable and
   refresh-survivable. This is the most-missed rule in table-heavy screens
   (tickets, receivables, payables).
3. **Local UI state → `useState`/`useReducer`** in the *nearest* owner: open/closed, hover, draft
   input. `useReducer` once 3+ fields change together or transitions have rules.
4. **Cross-cutting → context**, sparingly (auth/user, theme, notifications). Split providers by
   concern and keep values memoized — one god-context re-renders the whole app on any change.

- **Derive, don't duplicate.** Compute during render from the source of truth; no `useEffect` to
  sync two pieces of state (see `rerender-derived-state-no-effect`).
- **Single source of truth.** If two states can disagree, one must be derived.
- Reset child state on identity change with a `key`, not an effect.

## 4. TypeScript

- `strict: true` is on — keep it. **`tsc` gates `npm run build`.**
- **No `any`.** Use `unknown` + narrowing, a real interface, or a generic. If unavoidable, a
  comment must justify it. *(Baseline debt: 78 existing `any`s — don't add more; remove those you touch.)*
- **Type API responses at the boundary** (`interfaces/`) and use those types inward. Don't let
  `any` from `axios`/`dataProvider` leak into components.
- **Discriminated unions over optional-flag soup** — model states as
  `{status:"loading"} | {status:"error"; error:E} | {status:"ok"; data:D}`, so impossible
  combinations don't typecheck.
- Prefer `type` for unions/aliases, `interface` for object shapes that may be extended.
  No `I` prefix. `satisfies` to keep literal inference while checking a shape.
- `import type { … }` for type-only imports (lint enforces).
- Type props explicitly; avoid `React.FC` (obscures generics/children). Use
  `ComponentProps<typeof X>` to extend MUI component props rather than restating them.
- Never `@ts-ignore`; `@ts-expect-error` with a reason comment if truly needed.

## 5. Error Handling & Resilience

- **Error boundaries are mandatory.** Without one, a single render throw blanks the entire SPA.
  Wrap (a) the app shell and (b) each independently-failing panel — a dashboard card must not
  take down the page. Boundaries catch *render* errors only, never async/event-handler errors.
- **Every mutation handles failure.** Never fire-and-forget a write: on failure, surface a
  message, keep the user's input, and re-enable the control. Never swallow — no empty `catch`.
- **Map status codes to behaviour**, centrally in the provider/interceptor:
  `401` → re-auth; `403` → forbidden view (this repo has a `forbidden/` route);
  `422` → field-level form errors (§6); `5xx`/network → retryable "something went wrong".
- **Retries** only for idempotent reads (GET), bounded with backoff. **Never auto-retry a
  non-idempotent write** — retrying a credit approval or invoice post can double-apply it.
- Timeouts on every request; treat "no response" as a failure state, not a permanent spinner.
- Show three distinct states — **loading / empty / error** — and never conflate empty with error.
- Log with `console.error` and real context; **never log tokens, credentials, or customer PII**.

## 6. Forms & Validation (react-hook-form)

These screens move money — credit requests, invoices, dispatch. Treat forms as critical paths.

- **Schema-validate** (zod/yup + resolver) as the single source of truth for rules; infer the TS
  type from the schema so types and validation can't drift.
- **Validate on the server too, always.** Client validation is UX, never a trust boundary.
- **Prevent double submit:** disable the submit control while `isSubmitting`. A double-click that
  posts a payment twice is a data-integrity incident.
- **Map server field errors back onto fields** via `setError`, with a form-level message for
  non-field errors. Don't drop a 422 into a toast and lose which field was wrong.
- MUI inputs go through **`Controller`** (they're controlled); keep uncontrolled `register` where
  possible for fewer re-renders.
- Subscribe narrowly: **`useWatch` on the specific field**, never `watch()` on the whole form
  (re-renders everything per keystroke).
- Warn on navigate-away when `isDirty`. Reset via `reset()` after a successful submit.
- Money/quantity inputs: parse and validate as fixed-precision; enforce min/max and step; reject
  negatives explicitly rather than relying on the input type.
- Dates: the backend stores **UTC**. Convert at the boundary with `dayjs` and be explicit about
  timezone — naive local parsing produces off-by-one-day delivery dates.

## 7. Testing

No test framework is configured yet (**gap — recommend Vitest + React Testing Library + MSW**).
Until it exists, don't claim tests were run. Once present:

- **Vitest + RTL + `@testing-library/user-event`**; **MSW** to mock the API at the network layer.
- **Test behaviour, not implementation.** Query by role/label/text as a user would
  (`getByRole("button", {name:/approve/i})`); never assert on state internals or snapshot whole trees.
- **Cover per feature:** happy path; **empty, loading, and error states**; validation failures;
  permission-denied (RBAC) rendering; and the money/rounding edges.
- Test **custom hooks** directly (`renderHook`) — that's where logic should live and it's the
  cheapest place to assert it.
- Deterministic: fake timers, fixed clock (no `new Date()` in assertions), seeded data, no
  network, no `sleep`. Use builders/factories over giant literal fixtures.
- **Every bug fix ships a regression test** that fails before the fix.
- Priority when adding coverage to an untested codebase: money/credit logic → form validation →
  status transitions → table filtering. Don't chase a coverage % on presentational markup.

## 8. Performance

### Waterfalls (CRITICAL)

- **`async-parallel`** — independent requests in `Promise.all`, never sequential `await`s.
- **`async-cheap-condition-before-await`** — cheap sync checks (permission, empty input) first.
- **`async-defer-await`** — start the promise early, `await` only in the branch that needs it.
- **`async-dependencies`** — don't make C wait on A when only B depends on A.
- **`async-suspense-boundaries`** — `<Suspense>` per region so one slow panel doesn't block the screen.

```ts
// Bad — 3 sequential round trips
const ticket   = await api.getTicket(id);
const credit   = await api.getCredit(ticket.customerId);
const products = await api.listProducts();

// Good — products is independent; credit genuinely depends on ticket
const productsPromise = api.listProducts();
const ticket = await api.getTicket(id);
const [credit, products] = await Promise.all([
  api.getCredit(ticket.customerId),
  productsPromise,
]);
```

Never `await` inside a loop over rows — collect promises, then `Promise.all`.

### Bundle size (CRITICAL)

- **`bundle-barrel-imports`** — import concrete modules. Biggest win here; **52 existing barrel
  imports** are lint-flagged:

```ts
// Bad
import { Button, Dialog } from "@mui/material";
// Good
import Button from "@mui/material/Button";
import DeleteIcon from "@mui/icons-material/Delete";
```

  Type-only barrels (`interfaces/`) are fine — erased at compile time. Component barrels are not.
- **`bundle-dynamic-imports`** — `React.lazy` + `<Suspense>` for heavy/deferred UI: DataGrid
  screens, date pickers, charts, export/print views, large dialogs. Route-level splitting per
  `pages/<feature>` is the cheapest win.
- **`bundle-analyzable-paths`** — static literal import paths only; no template-string `import()`.
- **`bundle-conditional`** — load admin/export-only modules when activated, not at module scope.
- **`bundle-defer-third-party`** / **`bundle-preload`** — analytics after first paint; `import()`
  on nav hover/focus.
- Register `dayjs` plugins once at app setup, not per component.

### Data fetching

- Include **every** result-affecting parameter in the query key (filters, pagination, customer id)
  or you serve stale/cross-contaminated data.
- **Server-side** pagination/filtering for large tables; never fetch-all-and-filter-client-side.
- Invalidate precisely (affected resource/id) after mutations, not the whole cache.
- **`client-event-listeners`** one shared global listener, not one per row.
  **`client-passive-event-listeners`** `{passive:true}` for scroll/wheel/touch.
- **`client-localstorage-schema`** version and minimize persisted data; read once into memory
  (`js-cache-storage`), never in a render path.
- Ignore/abort stale in-flight responses so a slow earlier one can't overwrite a newer one.

### Re-renders

- **`rerender-derived-state-no-effect`** derive during render; no `useEffect`+`setState` to compute.
- **`rerender-no-inline-components`** never define a component inside a component — it remounts and
  loses state every parent render. **Includes DataGrid `renderCell`/`slots`** — hoist or `useCallback`.
  *(Live violation: `CreditProfileCard.tsx:52`.)*
- **`rerender-functional-setstate`** `setX(prev=>…)` keeps callbacks stable.
- **`rerender-defer-reads`** don't subscribe to state used only inside a callback.
- **`rerender-derived-state`** subscribe to the derived boolean, not the churning raw value.
- **`rerender-dependencies`** primitive deps, not freshly-built objects/arrays.
- **`rerender-lazy-state-init`** `useState(() => expensive())`.
- **`rerender-memo`** memoize genuinely expensive subtrees;
  **`rerender-simple-expression-in-memo`** don't memo a primitive comparison.
- **`rerender-memo-with-default-value`** hoist non-primitive defaults (`const EMPTY: readonly T[] = []`).
- **`rerender-split-combined-hooks`**, **`rerender-move-effect-to-event`**,
  **`rerender-transitions`** / **`rerender-use-deferred-value`** (responsive input over a big list),
  **`rerender-use-ref-transient-values`** (scroll/drag values).

### Rendering

- **`rendering-conditional-render`** ternary, not `&&` — `{count && <X/>}` renders a literal `0`.
- **Stable, data-derived `key`s** (`ticket.id`); never array index on reorderable/filterable rows.
- **`rendering-hoist-jsx`** static JSX to module scope. **`rendering-content-visibility`** +
  virtualization for long lists. **`rendering-usetransition-loading`**,
  **`rendering-activity`** (keep expensive panels mounted over remount-per-tab),
  **`rendering-animate-svg-wrapper`**, **`rendering-svg-precision`**,
  **`rendering-resource-hints`**, **`rendering-script-defer-async`**.

### JavaScript (lowest priority — never trade readability for these)

- **`js-set-map-lookups`/`js-index-maps`** build a `Map` once instead of `.find()` in a loop
  (the classic O(n²) in a table render).
- **`js-combine-iterations`**, **`js-flatmap-filter`**, **`js-early-exit`**,
  **`js-length-check-first`**, **`js-hoist-regexp`**, **`js-cache-property-access`**,
  **`js-cache-function-results`**, **`js-min-max-loop`**,
  **`js-tosorted-immutable`** (never mutate props/state in place), **`js-batch-dom-css`**,
  **`js-request-idle-callback`**.

## 9. Hooks Correctness

- Rules of Hooks: top level only, never in conditions/loops/early returns.
- **Complete dependency arrays.** Never silence the lint by deleting a dep — fix the design
  (hoist, ref, functional update, stable callback).
- **Effects synchronize with external systems** (subscriptions, listeners, imperative APIs) —
  not for deriving data or reacting to your own `setState`.
- **Always clean up**: listeners, timers, subscriptions, aborts. A missing cleanup is a leak
  and a set-state-after-unmount warning.
- **`advanced-use-latest`/`advanced-event-handler-refs`** stable callback identity without stale
  closures. **`advanced-effect-event-deps`**, **`advanced-init-once`** (app init once per load).

## 10. Security

- **Never `dangerouslySetInnerHTML`** with server/user content. If unavoidable, sanitize
  (DOMPurify) and justify in a comment. React escapes by default — don't defeat it.
- **Client-side authorization is display logic, not enforcement.** Hiding a button is UX; the
  backend must authorize every action. Never treat an RBAC check in the SPA as a control.
- **No secrets in the frontend.** Anything in `import.meta.env` shipped to the browser is public —
  no API keys or signing secrets. Only `VITE_`-prefixed public config.
- Tokens: prefer httpOnly cookies; if `localStorage` is used, accept the XSS exposure, keep TTLs
  short, and clear on logout. Never log or put a token in a URL/query param.
- Validate and allow-list any URL used in `href`/`src`/redirect (block `javascript:`, open redirects);
  `rel="noopener noreferrer"` on `target="_blank"`.
- Never render raw backend errors/stack traces to users; no PII or tokens in `console`.

## 11. Accessibility

- Semantic elements first (`button`, `nav`, `table`); ARIA only to fill genuine gaps.
- Every input has a **programmatically associated label**; errors linked via
  `aria-describedby` + `aria-invalid` (not colour alone).
- **Icon-only buttons need an accessible name** (`aria-label`).
- Keyboard reachable and operable; visible focus — never remove outlines without a replacement.
  Dialogs trap focus and restore it on close (MUI `Dialog` does this — don't fight it).
- Contrast ≥ 4.5:1 for body text; don't encode status by colour alone (add text/icon) — matters
  for status chips/badges anywhere in the UI.
- Announce async results (toast/`role="status"`), so a screen-reader user learns the save succeeded.
- Avoid `autoFocus` (jarring, disorienting) unless there's a strong, deliberate UX reason.

## 12. Tooling Gates

Run before calling work complete, from the app root:

```bash
npm run typecheck     # tsc --noEmit — must be clean
npm run lint          # eslint src (--max-warnings 0)
npm run build         # tsc && vite build — must succeed
# npm test            # once Vitest is set up
```

**Honest baseline (measured, as configured):**

- `npm run lint` → **237 problems (13 errors, 224 warnings)**: 78 `no-explicit-any`,
  52 MUI barrel imports, 45 unused vars, 41 type-import style.
- `npm run typecheck` / `npm run build` → **currently FAILING**. Most output is
  `node_modules/@refinedev/*` and a missing `@types/qs`; the `src/` errors are all in
  `ManagerSettingsPage.tsx` (`useFieldArray` not exported from the installed
  `react-hook-form`, plus two implicit `any`s). Fix those before relying on build as a gate.

This is pre-existing debt, not yours — but it means **"the build passes" is not currently a
signal**. Verify your change with `npm run lint` on the files you touched and by running the app.

- **Never introduce a new warning.** Leave files you touch at or below their previous count.
- Don't "fix" the baseline wholesale in an unrelated change — that buries the real diff.
- Never add `eslint-disable` without a reason comment; never disable a rule repo-wide to go green.
- `--max-warnings 0` means the baseline currently fails; treat *your* files as the gate until
  the debt is burned down.

## 13. AI Agent Rules

1. **Read neighbouring code first** and match existing patterns. Repo convention beats this doc.
2. **Follow the structure**: `pages/<feature>/` + `components/`, hooks for logic, `interfaces/` for
   shared types. Don't invent a parallel tree.
3. **Don't grow the known-oversized files** (§2) — extract the part you touch.
4. **No new `any`**, no `@ts-ignore`, no new lint warnings.
5. **Server state via Refine hooks**; URL state via `useSearchParams`. Never mirror server data
   into `useState`.
6. **Every async path gets loading, empty, and error states.** Every mutation handles failure.
7. **Never invent business rules** — credit limits, tax, rounding, status transitions, SLAs. Ask.
8. **Never guess at money or date semantics.** INR formatting via the shared helper; UTC↔local
   explicitly at the boundary.
9. **State assumptions** in your response when proceeding under ambiguity.
10. **Keep the diff focused** — no drive-by refactors or reformatting untouched files.
11. **Run the gates and report real output.** Never claim a typecheck/lint/test you didn't run.
    Say so plainly if one fails.
12. **Flag security-relevant changes** (auth, RBAC display, tokens, `dangerouslySetInnerHTML`,
    URL handling) in your summary.
13. **No commits unless asked.**

## 14. Review Checklist

Flag real defects only; cite `file:line` and the user-visible consequence.

**Architecture** — file over 250 lines or component over ~120? logic that belongs in a hook sitting
in JSX? component defined inside a component? prop-drilling past 2 levels? duplication that should
be extracted, or premature abstraction that shouldn't?

**Naming** — domain-accurate, not `data`/`tmp`/`item`? `handle*`/`on*` split right? booleans
`is/has/can`? units in the name? magic numbers/strings replaced by named constants?

**State** — server data mirrored into `useState`? filters/pagination/tab in component state instead
of the URL? two states that can disagree? `useEffect`+`setState` deriving what render could compute?
context value unmemoized or over-broad?

**Types** — new `any`/`@ts-ignore`? API response typed at the boundary? optional-flag soup where a
discriminated union belongs? `tsc` clean?

**Errors** — error boundary covering this subtree? mutation failure surfaced and input preserved?
empty `catch`? 401/403/422/5xx distinguished? non-idempotent write auto-retried? loading/empty/error
all present? PII or tokens logged?

**Forms** — schema validation? submit disabled while submitting (double-post risk)? server field
errors mapped back? `watch()` on the whole form? dirty-navigation guard? money precision and
timezone handled explicitly?

**Testing** — new logic covered incl. error/empty/permission paths? behaviour not implementation?
deterministic (no real clock/network)? regression test for a bug fix?

**Performance** — sequential awaits that could be parallel? `await` in a loop? MUI barrel import?
heavy component not lazy? query key missing a parameter? unbounded list fetch? `.find()` in a
render loop? array index as `key`? `&&` with a numeric left side?

**Hooks** — conditional hook? dep array incomplete or suppressed? missing cleanup?

**Security** — `dangerouslySetInnerHTML`? client-side RBAC treated as enforcement? secret in
`import.meta.env`? unvalidated URL/redirect? missing `noopener`? raw backend error shown to user?

**A11y** — inputs labelled and errors associated? icon-only button named? keyboard reachable, focus
visible? status conveyed by colour alone? `autoFocus` added?

**Gates** — typecheck, lint, build green; no new warnings in touched files; no unexplained
`eslint-disable`.