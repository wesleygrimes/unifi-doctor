"""Tests for topology/renderer.py — ASCII canvas and map rendering."""

from __future__ import annotations

from unifi_doctor.models.types import APLink, APPlacement, BarrierType, FloorLevel, Topology
from unifi_doctor.topology.layout import LayoutResult, compute_layout
from unifi_doctor.topology.renderer import AsciiCanvas, render_legend, render_topology_map


def test_canvas_put_char():
    canvas = AsciiCanvas(width=10, height=5)
    canvas.put_char(3, 2, "X", "bold")
    assert canvas.get_char(3, 2) == "X"
    assert canvas.grid[2][3].style == "bold"


def test_canvas_put_char_out_of_bounds():
    canvas = AsciiCanvas(width=10, height=5)
    canvas.put_char(-1, 0, "X")
    canvas.put_char(10, 0, "X")
    canvas.put_char(0, -1, "X")
    canvas.put_char(0, 5, "X")
    # No crash, canvas unchanged
    assert canvas.get_char(0, 0) == " "


def test_canvas_put_text():
    canvas = AsciiCanvas(width=20, height=3)
    canvas.put_text(5, 1, "hello", "green")
    assert canvas.get_char(5, 1) == "h"
    assert canvas.get_char(6, 1) == "e"
    assert canvas.get_char(7, 1) == "l"
    assert canvas.get_char(8, 1) == "l"
    assert canvas.get_char(9, 1) == "o"


def test_canvas_draw_line_horizontal():
    canvas = AsciiCanvas(width=10, height=3)
    canvas.draw_line(2, 1, 7, 1, char="-")
    for x in range(2, 8):
        assert canvas.get_char(x, 1) == "-"


def test_canvas_draw_line_vertical():
    canvas = AsciiCanvas(width=5, height=10)
    canvas.draw_line(2, 1, 2, 6, char="|")
    for y in range(1, 7):
        assert canvas.get_char(2, y) == "|"


def test_bresenham_diagonal():
    canvas = AsciiCanvas(width=10, height=10)
    canvas.draw_line(0, 0, 5, 5, char="*")
    # Diagonal should hit at least the start and end
    assert canvas.get_char(0, 0) == "*"
    assert canvas.get_char(5, 5) == "*"


def test_draw_line_does_not_overwrite_nodes():
    canvas = AsciiCanvas(width=10, height=3)
    canvas.put_char(5, 1, "@", "bold green")
    canvas.draw_line(0, 1, 9, 1, char="-")
    # Node marker should be preserved
    assert canvas.get_char(5, 1) == "@"


def test_canvas_to_rich_text():
    canvas = AsciiCanvas(width=3, height=2)
    canvas.put_char(0, 0, "A", "red")
    canvas.put_char(1, 0, "B")
    text = canvas.to_rich_text()
    plain = text.plain
    assert "A" in plain
    assert "B" in plain
    assert "\n" in plain


def test_render_single_ap():
    topo = Topology(
        placements=[APPlacement(mac="aa:bb:cc:dd:ee:00", name="LivingRoom", floor=FloorLevel.GROUND)]
    )
    layout = compute_layout(topo)
    panel = render_topology_map(topo, layout, canvas_width=40, canvas_height=10)
    # Panel should contain the AP name
    assert panel.title is not None


def test_render_multi_ap():
    topo = Topology(
        placements=[
            APPlacement(mac="aa:bb:cc:dd:ee:00", name="AP-1", floor=FloorLevel.GROUND),
            APPlacement(mac="aa:bb:cc:dd:ee:01", name="AP-2", floor=FloorLevel.UPPER),
            APPlacement(mac="aa:bb:cc:dd:ee:02", name="AP-3", floor=FloorLevel.BASEMENT),
        ],
        links=[
            APLink(
                ap1_mac="aa:bb:cc:dd:ee:00",
                ap2_mac="aa:bb:cc:dd:ee:01",
                distance_ft=30,
                barrier=BarrierType.WALL,
            ),
        ],
    )
    layout = compute_layout(topo)
    panel = render_topology_map(topo, layout, canvas_width=60, canvas_height=15)
    assert panel is not None


def test_render_with_client_counts():
    topo = Topology(
        placements=[
            APPlacement(mac="aa:bb:cc:dd:ee:00", name="Office", floor=FloorLevel.GROUND),
            APPlacement(mac="aa:bb:cc:dd:ee:01", name="Kitchen", floor=FloorLevel.GROUND),
        ]
    )
    layout = compute_layout(topo)
    client_counts = {"aa:bb:cc:dd:ee:00": 12, "aa:bb:cc:dd:ee:01": 5}
    panel = render_topology_map(topo, layout, canvas_width=60, canvas_height=15, client_counts=client_counts)
    assert panel is not None


def test_render_empty_topology():
    topo = Topology()
    layout = LayoutResult()
    panel = render_topology_map(topo, layout, canvas_width=40, canvas_height=10)
    assert panel is not None


def test_render_legend():
    panel = render_legend()
    assert panel is not None
    assert panel.title is not None
