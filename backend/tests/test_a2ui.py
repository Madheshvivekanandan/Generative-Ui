"""The compiler and sanitizer are pure functions -- the highest-value tests in
the repo, because everything the browser draws passes through them."""

import pytest

import a2ui
from schemas import (
    BarChart,
    BlockAction,
    Column,
    DataTable,
    DonutChart,
    LineChart,
    Point,
    Series,
    Slice,
    StatCard,
)


def make_actions(count: int) -> list[BlockAction]:
    return [BlockAction(label=f"Action {i}", prompt=f"Do thing {i}") for i in range(count)]


def make_series(count: int, points: int = 3) -> list[Series]:
    return [
        Series(name=f"S{i}", points=[Point(x=f"x{p}", y=float(p)) for p in range(points)])
        for i in range(count)
    ]


def make_line(series: list[Series], actions: list[BlockAction] | None = None) -> LineChart:
    return LineChart(
        type="line_chart",
        title="T",
        x_label="Month",
        y_label="USD",
        unit="USD",
        series=series,
        actions=actions or [],
    )


def make_stat(actions: list[BlockAction] | None = None) -> StatCard:
    return StatCard(
        type="stat_card",
        title="Revenue",
        value=1.0,
        unit="USD",
        delta_pct=0.0,
        delta_direction="flat",
        caption="",
        actions=actions or [],
    )


# --- sanitize ---------------------------------------------------------------


def test_sanitize_trims_series_and_points_to_limits():
    block = a2ui.sanitize(make_line(make_series(9, points=40)))
    assert len(block.series) == a2ui.MAX_SERIES
    assert all(len(s.points) == a2ui.MAX_POINTS for s in block.series)


def test_sanitize_chart_with_no_series_raises():
    with pytest.raises(ValueError):
        a2ui.sanitize(make_line([]))


def test_sanitize_chart_with_only_empty_series_raises():
    with pytest.raises(ValueError):
        a2ui.sanitize(make_line(make_series(2, points=0)))


def test_sanitize_caps_actions_at_two():
    block = a2ui.sanitize(make_line(make_series(1), actions=make_actions(4)))
    assert len(block.actions) == a2ui.MAX_ACTIONS


def test_sanitize_donut_drops_nonpositive_and_caps_slices():
    slices = [Slice(label=f"s{i}", value=float(i)) for i in range(9)]  # s0 has value 0
    block = a2ui.sanitize(
        DonutChart(type="donut_chart", title="T", unit="USD", slices=slices, actions=[])
    )
    assert len(block.slices) == a2ui.MAX_SLICES
    assert all(s.value > 0 for s in block.slices)


def test_sanitize_one_slice_donut_raises():
    slices = [Slice(label="only", value=5.0), Slice(label="zero", value=0.0)]
    with pytest.raises(ValueError):
        a2ui.sanitize(
            DonutChart(type="donut_chart", title="T", unit="USD", slices=slices, actions=[])
        )


def make_table(rows: list[list[str]]) -> DataTable:
    columns = [
        Column(key="a", label="A", align="left"),
        Column(key="b", label="B", align="right"),
    ]
    return DataTable(type="data_table", title="T", columns=columns, rows=rows, actions=[])


def test_sanitize_drops_ragged_table_rows():
    block = a2ui.sanitize(make_table([["1", "2"], ["only-one-cell"], ["3", "4"]]))
    assert block.rows == [["1", "2"], ["3", "4"]]


def test_sanitize_table_with_no_wellformed_rows_raises():
    with pytest.raises(ValueError):
        a2ui.sanitize(make_table([["just-one"], ["a", "b", "c"]]))


# --- the compiler -----------------------------------------------------------


def test_group_children_packs_consecutive_stat_cards_into_a_row():
    blocks = [make_stat(), make_stat(), make_line(make_series(1)), make_stat()]
    rows, children, in_row = a2ui.group_children(blocks)

    assert children == ["tilerow0", "b2", "b3"]
    assert in_row == {"b0", "b1"}
    assert rows == [
        {"id": "tilerow0", "component": "Row", "children": ["b0", "b1"], "align": "stretch"}
    ]


def test_component_tree_weights_only_row_packed_cards():
    tree = a2ui.component_tree([make_stat(), make_stat()])
    by_id = {c["id"]: c for c in tree}
    assert by_id["b0"]["weight"] == 1 and by_id["b1"]["weight"] == 1

    solo = {c["id"]: c for c in a2ui.component_tree([make_stat()])}
    assert "weight" not in solo["b0"]


def test_compile_block_binds_props_to_the_data_model():
    view = next(c for c in a2ui.compile_block(make_line(make_series(1)), 3) if c["id"] == "b3_view")
    assert view["series"] == {"path": "/blocks/3/series"}
    assert view["component"] == "LineChart"


def test_compile_block_buttons_carry_the_refine_action_context():
    action = BlockAction(label="Split by region", prompt="Break revenue down by region")
    components = a2ui.compile_block(make_stat(actions=[action]), 0)
    button = next(c for c in components if c["component"] == "Button")
    event = button["action"]["event"]
    assert event["name"] == a2ui.REFINE_ACTION
    assert event["context"] == {"prompt": action.prompt, "label": action.label}


def test_full_surface_sends_data_before_components():
    messages = a2ui.full_surface("dashboard", [make_stat()])
    order = [next(iter(set(m) - {"version"})) for m in messages]
    assert order == ["createSurface", "updateDataModel", "updateComponents"]
    assert messages[1]["updateDataModel"]["path"] == "/"


def test_block_data_strips_type_and_actions():
    data = a2ui.block_data(make_stat(actions=make_actions(1)))
    assert "type" not in data and "actions" not in data
    assert data["title"] == "Revenue"
