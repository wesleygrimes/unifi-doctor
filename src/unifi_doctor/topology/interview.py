"""First-run topology interview — gathers physical placement of APs."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
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
BACKHAUL_CHOICES = {str(i + 1): b for i, b in enumerate(BackhaulType)}
BARRIER_CHOICES = {str(i + 1): b for i, b in enumerate(BarrierType)}


def run_interview(aps: list[DeviceInfo]) -> Topology:
    """Run the interactive topology interview for discovered APs."""
    existing = load_topology()

    console.print(
        Panel(
            "[bold cyan]UniFi Doctor — Topology Setup[/bold cyan]\n\n"
            "I'll ask about where each AP is physically located and how they\n"
            "connect to each other. This helps me contextualize signal readings.",
            title="Setup",
        )
    )

    if not aps:
        console.print("[yellow]No APs discovered. Run setup again after adopting APs.[/yellow]")
        return existing

    # ------- AP Placements -------
    console.print(f"\n[bold]Found {len(aps)} access point(s):[/bold]")
    table = Table(show_header=True)
    table.add_column("AP", style="cyan")
    table.add_column("MAC")
    table.add_column("Model")
    table.add_column("IP")
    for ap in aps:
        table.add_row(ap.display_name, ap.mac, ap.model, ap.ip)
    console.print(table)

    placements: list[APPlacement] = []

    for ap in aps:
        console.print(f"\n[bold underline]{ap.display_name}[/bold underline] ({ap.mac})")

        # Floor
        console.print("  Floor options: [1] Ground  [2] Upper  [3] Basement  [4] Detached")
        floor_choice = Prompt.ask("  Floor", choices=["1", "2", "3", "4"], default="1")
        floor = FLOOR_CHOICES[floor_choice]

        # Location description
        location = Prompt.ask("  Location description (e.g., 'living room ceiling')", default="")

        # Backhaul
        console.print("  Backhaul: [1] Wired (Ethernet)  [2] Wireless Mesh")
        bh_choice = Prompt.ask("  Backhaul type", choices=["1", "2"], default="1")
        backhaul = BACKHAUL_CHOICES[bh_choice]

        placements.append(
            APPlacement(
                mac=ap.mac,
                name=ap.display_name,
                floor=floor,
                location_description=location,
                backhaul=backhaul,
            )
        )

    # ------- AP Links (pairwise distances) -------
    links: list[APLink] = []

    if len(aps) > 1:
        console.print("\n[bold]Now let's map distances between APs.[/bold]")
        console.print("[dim]This helps determine if power levels or signal readings make sense.[/dim]\n")

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
