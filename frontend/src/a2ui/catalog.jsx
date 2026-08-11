/**
 * Our A2UI component catalog.
 *
 * A2UI's basic catalog has no charts, so the six financial views are
 * registered here as custom components on top of it. The agent may only name
 * components that appear in this catalog -- that whitelist is the security
 * boundary of the whole design, and it is enforced by the renderer, not by
 * anything we remember to check.
 *
 * Each component is declared twice by design: a Zod schema describing its
 * public API (what the agent may set, and whether each prop accepts a
 * `{path: ...}` binding), and a React implementation that receives already
 * resolved values. A2UI's generic binder sits between them and does the
 * resolving, so the views never see a binding object.
 *
 * `catalogId` must match `CATALOG_ID` in `backend/a2ui.py`. It is an
 * identifier, never fetched.
 */

import { Catalog, CommonSchemas } from '@a2ui/web_core/v0_9'
import {
  AudioPlayer,
  Button,
  CheckBox,
  ChoicePicker,
  Column,
  DateTimeInput,
  Divider,
  Icon,
  Image,
  List,
  Modal,
  Row,
  Slider,
  Tabs,
  Text,
  TextField,
  Video,
  basicCatalog,
  createComponentImplementation,
} from '@a2ui/react/v0_9'
import { z } from 'zod'

import ErrorBoundary from '../components/ErrorBoundary'
import {
  BarChartView,
  DataTableView,
  DonutChartView,
  LineChartView,
  StatCardView,
  TextNoteView,
} from './views'

export const CATALOG_ID = 'https://acme.analytics/catalogs/finance/v1.json'

const { DynamicString, DynamicNumber, DynamicBoolean, DynamicValue } = CommonSchemas

// Every prop is optional: the data model is written by an agent and can be
// mid-stream when a component first renders. The views already degrade to an
// em dash, so a missing prop must not be a schema violation.
const dynamicString = DynamicString.optional()
const dynamicNumber = DynamicNumber.optional()
const dynamicList = DynamicValue.optional()

/**
 * `Card` replaces A2UI's own, for one reason: the error boundary.
 *
 * A card is the unit of failure in this dashboard -- a malformed component must
 * be able to break its own card and nothing else. A boundary around the whole
 * surface would let one bad chart blank an entire answer, so the boundary has
 * to live at the card, which means owning the component that draws it.
 */
const CardApi = {
  name: 'Card',
  schema: z.object({
    child: CommonSchemas.ComponentId.optional(),
    // A2UI's flex-grow, set by the compiler on cards that share a Row so they
    // divide the width evenly instead of collapsing to their content.
    weight: z.number().optional(),
  }),
}

const Card = createComponentImplementation(CardApi, ({ props, buildChild }) => (
  // We draw the element, so we are the ones who have to honour `weight`;
  // A2UI's own components apply it to their own root the same way.
  <section className="card" style={props.weight ? { flexGrow: props.weight } : undefined}>
    <ErrorBoundary>{props.child ? buildChild(props.child) : null}</ErrorBoundary>
  </section>
))

const StatCardApi = {
  name: 'StatCard',
  schema: z.object({
    title: dynamicString,
    value: dynamicNumber,
    unit: dynamicString,
    delta_pct: dynamicNumber,
    delta_direction: dynamicString,
    caption: dynamicString,
  }),
}

const StatCard = createComponentImplementation(StatCardApi, ({ props }) => (
  <StatCardView
    title={props.title}
    value={props.value}
    unit={props.unit}
    deltaPct={props.delta_pct}
    deltaDirection={props.delta_direction}
    caption={props.caption}
  />
))

const LineChartApi = {
  name: 'LineChart',
  schema: z.object({
    series: dynamicList,
    unit: dynamicString,
    x_label: dynamicString,
    y_label: dynamicString,
  }),
}

const LineChart = createComponentImplementation(LineChartApi, ({ props }) => (
  <LineChartView
    series={props.series}
    unit={props.unit}
    xLabel={props.x_label}
    yLabel={props.y_label}
  />
))

const BarChartApi = {
  name: 'BarChart',
  schema: z.object({
    series: dynamicList,
    unit: dynamicString,
    x_label: dynamicString,
    y_label: dynamicString,
    stacked: DynamicBoolean.optional(),
  }),
}

const BarChart = createComponentImplementation(BarChartApi, ({ props }) => (
  <BarChartView
    series={props.series}
    unit={props.unit}
    xLabel={props.x_label}
    yLabel={props.y_label}
    stacked={props.stacked}
  />
))

const DonutChartApi = {
  name: 'DonutChart',
  schema: z.object({
    slices: dynamicList,
    unit: dynamicString,
  }),
}

const DonutChart = createComponentImplementation(DonutChartApi, ({ props }) => (
  <DonutChartView slices={props.slices} unit={props.unit} />
))

const DataTableApi = {
  name: 'DataTable',
  schema: z.object({
    columns: dynamicList,
    rows: dynamicList,
  }),
}

const DataTable = createComponentImplementation(DataTableApi, ({ props }) => (
  <DataTableView columns={props.columns} rows={props.rows} />
))

const TextNoteApi = {
  name: 'TextNote',
  schema: z.object({
    body: dynamicString,
  }),
}

const TextNote = createComponentImplementation(TextNoteApi, ({ props }) => (
  <TextNoteView body={props.body} />
))

/**
 * The catalog the agent generates against: A2UI's standard components for
 * structure, ours for the data.
 *
 * The basic components are listed explicitly rather than spread from
 * `basicCatalog` so this file is an honest inventory of what an agent is
 * allowed to put on screen. Its logic functions (`formatString`, `required`,
 * the validation helpers) are carried over as-is.
 */
export const financeCatalog = new Catalog(
  CATALOG_ID,
  [
    // Structure and content, from A2UI's basic catalog.
    Column,
    Row,
    List,
    Tabs,
    Modal,
    Divider,
    Text,
    Image,
    Icon,
    Video,
    AudioPlayer,
    // Input, so an agent can put controls on a card.
    Button,
    TextField,
    CheckBox,
    ChoicePicker,
    Slider,
    DateTimeInput,
    // Ours.
    Card,
    StatCard,
    LineChart,
    BarChart,
    DonutChart,
    DataTable,
    TextNote,
  ],
  [...basicCatalog.functions.values()],
)
