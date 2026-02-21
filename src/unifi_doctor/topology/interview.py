"""First-run topology interview — gathers physical placement of APs."""

from __future__ import annotations

import re

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from unifi_doctor.api.client import load_topology, save_topology
from unifi_doctor.models.types import (
    APLink,
    APPlacement,
    BackhaulType,
    BarrierType,
    DeviceInfo,
    FloorLevel,
    Topology,
)

console = Console()

FLOOR_CHOICES = {str(i + 1): f for i, f in enumerate(FloorLevel)}
BARRIER_CHOICES = {str(i + 1): b for i, b in enumerate(BarrierType)}

# Keywords in AP names that suggest an outdoor / detached placement
_OUTDOOR_KEYWORDS = re.compile(r"shed|garage|outdoor|patio|yard|porch|deck", re.IGNORECASE)


def _detect_backhaul(ap: DeviceInfo, all_devices: list[DeviceInfo]) -> BackhaulType:
    """Detect backhaul type from device data instead of asking the user."""
    if ap.mesh_sta_vap_enabled or ap.uplink_type == "wireless":
        return BackhaulType.WIRELESS_MESH
    return BackhaulType.WIRED


def _default_floor(ap: DeviceInfo) -> str:
    """Return a smart default floor choice based on AP name."""
    if _OUTDOOR_KEYWORDS.search(ap.display_name):
        return "4"  # DETACHED
    return "1"  # GROUND


def _parse_floor_location(raw: str) -> tuple[FloorLevel, str]:
    """Parse a combined 'floor, location' input string.

    Accepts formats like:
      "ground, hallway ceiling"  → (GROUND, "hallway ceiling")
      "2, living room"           → (UPPER, "living room")
      "ground"                   → (GROUND, "")
      "4"                        → (DETACHED, "")
    """
    # Split on first comma
    parts = [p.strip() for p in raw.split(",", maxsplit=1)]
    floor_part = parts[0].lower()
    location = parts[1] if len(parts) > 1 else ""

    # Try numeric choice first
    if floor_part in FLOOR_CHOICES:
        return FLOOR_CHOICES[floor_part], location

    # Try matching enum value names
    name_map = {f.value: f for f in FloorLevel}
    if floor_part in name_map:
        return name_map[floor_part], location

    # Fallback to ground
    return FloorLevel.GROUND, location


def run_interview(aps: list[DeviceInfo], all_devices: list[DeviceInfo] | None = None) -> Topology:
    """Run the interactive topology interview for discovered APs."""
    existing = load_topology()

    if all_devices is None:
        all_devices = aps

    console.print(
        Panel(
            "[bold cyan]UniFi Doctor — Topology Setup[/bold cyan]\n\n"
            "I'll ask about where each AP is physically located.\n"
            "Backhaul type (wired/mesh) is auto-detected from device data.",
            title="Setup",
        )
    )

    if not aps:
        console.print("[yellow]No APs discovered. Run setup again after adopting APs.[/yellow]")
        return existing

    # ------- AP table -------
    console.print(f"\n[bold]Found {len(aps)} access point(s):[/bold]")
    table = Table(show_header=True)
    table.add_column("AP", style="cyan")
    table.add_column("MAC")
    table.add_column("Model")
    table.add_column("IP")
    table.add_column("Backhaul")
    for ap in aps:
        backhaul = _detect_backhaul(ap, all_devices)
        table.add_row(ap.display_name, ap.mac, ap.model, ap.ip, backhaul.value)
    console.print(table)

    # ------- AP Placements -------
    placements: list[APPlacement] = []

    console.print(
        "\n[dim]For each AP, enter floor and location."
        "\nFloors: [1] ground  [2] upper  [3] basement  [4] detached"
        "\nFormat: 'floor, location' (e.g. 'ground, hallway ceiling') or just 'ground'[/dim]\n"
    )

    for ap in aps:
        backhaul = _detect_backhaul(ap, all_devices)
        default = _default_floor(ap)
        default_label = FLOOR_CHOICES[default].value

        raw = Prompt.ask(
            f"  [bold]{ap.display_name}[/bold] — floor, location",
            default=default_label,
        )

        floor, location = _parse_floor_location(raw)

        placements.append(
            APPlacement(
                mac=ap.mac,
                name=ap.display_name,
                floor=floor,
                location_description=location,
                backhaul=backhaul,
            )
        )

    # ------- AP Links (opt-in) -------
    links: list[APLink] = []

    if len(aps) > 1:
        map_distances = Confirm.ask(
            "\n[bold]Map distances between APs?[/bold] (helps with power analysis)",
            default=False,
        )

        if map_distances:
            console.print()
            for i in range(len(aps)):
                for j in range(i + 1, len(aps)):
                    ap1, ap2 = aps[i], aps[j]
                    console.print(f"  [cyan]{ap1.display_name}[/cyan] ↔ [cyan]{ap2.display_name}[/cyan]")
                    dist = IntPrompt.ask("    Distance in feet (approximate)", default=30)

                    console.print("    Barrier: [1] Wall  [2] Floor/Ceiling  [3] Outdoor  [4] Open Air")
                    bar_choice = Prompt.ask("    Barrier type", choices=["1", "2", "3", "4"], default="1")
                    barrier = BARRIER_CHOICES[bar_choice]

                    links.append(
                        APLink(
                            ap1_mac=ap1.mac,
                            ap2_mac=ap2.mac,
                            distance_ft=dist,
                            barrier=barrier,
                        )
                    )

    topology = Topology(placements=placements, links=links)
    save_topology(topology)
    console.print("\n[green]Topology saved to ~/.unifi-doctor/topology.yaml[/green]")
    return topology
