"""ASCII canvas and topology map renderer."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.panel import Panel
from rich.text import Text

from unifi_doctor.models.types import BarrierType, FloorLevel, Topology
from unifi_doctor.topology.layout import LayoutResult

# ---------------------------------------------------------------------------
# Floor color mapping
# ---------------------------------------------------------------------------

FLOOR_STYLES: dict[FloorLevel, str] = {
    FloorLevel.GROUND: "green",
    FloorLevel.UPPER: "cyan",
    FloorLevel.BASEMENT: "yellow",
    FloorLevel.DETACHED: "magenta",
}

BARRIER_CHARS: dict[BarrierType, str] = {
    BarrierType.OPEN_AIR: "-",
    BarrierType.WALL: "=",
    BarrierType.FLOOR_CEILING: "#",
    BarrierType.OUTDOOR: ".",
}


# ---------------------------------------------------------------------------
# ASCII Canvas
# ---------------------------------------------------------------------------


@dataclass
class GridCell:
    char: str = " "
    style: str = ""


@dataclass
class AsciiCanvas:
    width: int
    height: int
    grid: list[list[GridCell]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.grid:
            self.grid = [[GridCell() for _ in range(self.width)] for _ in range(self.height)]

    def put_char(self, x: int, y: int, char: str, style: str = "") -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.grid[y][x] = GridCell(char=char, style=style)

    def put_text(self, x: int, y: int, text: str, style: str = "") -> None:
        for i, ch in enumerate(text):
            self.put_char(x + i, y, ch, style)

    def get_char(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x].char
        return " "

    def draw_line(self, x0: int, y0: int, x1: int, y1: int, char: str = "-", style: str = "") -> None:
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        while True:
            # Don't overwrite node markers
            if self.get_char(x0, y0) not in ("@", "[", "]"):
                self.put_char(x0, y0, char, style)

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def to_rich_text(self) -> Text:
        text = Text()
        for row_idx, row in enumerate(self.grid):
            for cell in row:
                if cell.style:
                    text.append(cell.char, style=cell.style)
                else:
                    text.append(cell.char)
            if row_idx < self.height - 1:
                text.append("\n")
        return text


# ---------------------------------------------------------------------------
# Topology Map Renderer
# ---------------------------------------------------------------------------

# Aspect ratio compensation: terminal chars are ~2x taller than wide
ASPECT_RATIO = 2.0


def _floor_abbrev(floor: FloorLevel) -> str:
    return {"ground": "G", "upper": "U", "basement": "B", "detached": "D"}.get(floor.value, "?")


def _try_place_label(
    canvas: AsciiCanvas,
    cx: int,
    cy: int,
    label: str,
    style: str,
    max_label_len: int = 15,
) -> None:
    """Try to place a label near a node, checking multiple positions."""
    if len(label) > max_label_len:
        label = label[: max_label_len - 1] + "~"

    label_len = len(label)

    # Candidates: right, left, below, above
    candidates = [
        (cx + 2, cy),  # right
        (cx - label_len - 1, cy),  # left
        (cx - label_len // 2, cy + 1),  # below
        (cx - label_len // 2, cy - 1),  # above
    ]

    for lx, ly in candidates:
        if lx < 0 or ly < 0 or lx + label_len > canvas.width or ly >= canvas.height:
            continue
        # Check if space is clear
        clear = all(canvas.get_char(lx + i, ly) == " " for i in range(label_len))
        if clear:
            canvas.put_text(lx, ly, label, style)
            return

    # Fallback: place right even if overlapping
    lx, ly = cx + 2, cy
    if 0 <= ly < canvas.height:
        end = min(lx + label_len, canvas.width)
        canvas.put_text(lx, ly, label[: end - lx], style)


def render_topology_map(
    topology: Topology,
    layout: LayoutResult,
    *,
    canvas_width: int = 80,
    canvas_height: int = 24,
    client_counts: dict[str, int] | None = None,
) -> Panel:
    """Render the topology as an ASCII map inside a Rich Panel."""
    canvas = AsciiCanvas(width=canvas_width, height=canvas_height)

    if not layout.positions:
        canvas.put_text(canvas_width // 2 - 8, canvas_height // 2, "No APs configured", "dim")
        return Panel(canvas.to_rich_text(), title="[bold cyan]Topology Map[/bold cyan]", border_style="cyan")

    # Build placement lookup for floor info
    placement_lookup = {p.mac: p for p in topology.placements}

    # Build link lookup
    link_lookup: dict[tuple[str, str], tuple[float, BarrierType]] = {}
    for link in topology.links:
        key = tuple(sorted([link.ap1_mac, link.ap2_mac]))
        link_lookup[key] = (link.distance_ft, link.barrier)  # type: ignore[assignment]

    # Map normalized positions to canvas coordinates
    # Account for aspect ratio: x range is full width, y range accounts for taller chars
    node_coords: dict[str, tuple[int, int]] = {}
    for pos in layout.positions:
        cx = int(pos.x * (canvas_width - 1))
        cy = int(pos.y * (canvas_height - 1))
        # Clamp to safe bounds
        cx = max(1, min(canvas_width - 2, cx))
        cy = max(1, min(canvas_height - 2, cy))
        node_coords[pos.mac] = (cx, cy)

    # Draw connection lines first (so nodes draw on top)
    for (mac_a, mac_b), (dist_ft, barrier) in link_lookup.items():
        if mac_a in node_coords and mac_b in node_coords:
            x0, y0 = node_coords[mac_a]
            x1, y1 = node_coords[mac_b]
            line_char = BARRIER_CHARS.get(barrier, "-")
            canvas.draw_line(x0, y0, x1, y1, char=line_char, style="dim")

            # Distance label at midpoint
            mid_x = (x0 + x1) // 2
            mid_y = (y0 + y1) // 2
            dist_label = f"{int(dist_ft)}ft"
            label_x = mid_x - len(dist_label) // 2
            if 0 <= label_x and label_x + len(dist_label) < canvas_width and 0 <= mid_y < canvas_height:
                canvas.put_text(label_x, mid_y, dist_label, "dim italic")

    # Draw nodes and labels
    for pos in layout.positions:
        cx, cy = node_coords[pos.mac]
        placement = placement_lookup.get(pos.mac)
        floor = placement.floor if placement else FloorLevel.GROUND
        style = FLOOR_STYLES.get(floor, "white")

        # Draw node marker
        canvas.put_char(cx, cy, "@", f"bold {style}")

        # Build label
        floor_tag = _floor_abbrev(floor)
        label = f"{pos.name}[{floor_tag}]"
        if client_counts and pos.mac in client_counts:
            label += f" ({client_counts[pos.mac]})"

        _try_place_label(canvas, cx, cy, label, style)

    return Panel(canvas.to_rich_text(), title="[bold cyan]Topology Map[/bold cyan]", border_style="cyan")


def render_legend() -> Panel:
    """Render a legend panel explaining map symbols."""
    text = Text()
    text.append("  @ ", style="bold white")
    text.append("Access Point    ")
    text.append("- ", style="dim")
    text.append("Open Air    ")
    text.append("= ", style="dim")
    text.append("Wall    ")
    text.append("# ", style="dim")
    text.append("Floor/Ceiling    ")
    text.append(". ", style="dim")
    text.append("Outdoor\n")

    text.append("  Floors: ")
    text.append("G", style="bold green")
    text.append("round  ")
    text.append("U", style="bold cyan")
    text.append("pper  ")
    text.append("B", style="bold yellow")
    text.append("asement  ")
    text.append("D", style="bold magenta")
    text.append("etached")

    return Panel(text, title="[dim]Legend[/dim]", border_style="dim")
