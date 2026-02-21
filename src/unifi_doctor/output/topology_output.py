"""Output orchestration for the topology map command."""

from __future__ import annotations

from rich.console import Console

from unifi_doctor.models.types import APCoordinate, FloorLevel, Topology, TopologyMapResult
from unifi_doctor.topology.layout import compute_layout
from unifi_doctor.topology.renderer import render_legend, render_topology_map

console = Console()


def print_topology_map(topology: Topology, *, client_counts: dict[str, int] | None = None) -> None:
    """Compute layout, render, and print the topology map."""
    layout = compute_layout(topology)

    # Auto-size canvas to terminal width
    width = min(console.width - 4, 120)  # leave room for panel borders
    height = max(16, width // 4)  # reasonable aspect ratio

    map_panel = render_topology_map(
        topology, layout, canvas_width=width, canvas_height=height, client_counts=client_counts
    )
    legend = render_legend()

    console.print()
    console.print(map_panel)
    console.print(legend)
    console.print()


def topology_to_json(
    topology: Topology,
    *,
    client_counts: dict[str, int] | None = None,
) -> dict:
    """Build a JSON-serializable dict of topology coordinates and links."""
    layout = compute_layout(topology)
    placement_lookup = {p.mac: p for p in topology.placements}

    nodes = []
    for pos in layout.positions:
        placement = placement_lookup.get(pos.mac)
        floor = placement.floor if placement else FloorLevel.GROUND
        count = client_counts.get(pos.mac) if client_counts else None
        nodes.append(
            APCoordinate(
                mac=pos.mac,
                name=pos.name,
                floor=floor,
                x=round(pos.x, 4),
                y=round(pos.y, 4),
                client_count=count,
            )
        )

    result = TopologyMapResult(nodes=nodes, links=topology.links)
    return result.model_dump(mode="json")
