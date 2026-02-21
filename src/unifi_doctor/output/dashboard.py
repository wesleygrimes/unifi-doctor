"""Live watch mode dashboard using rich.live."""

from __future__ import annotations

import asyncio
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from unifi_doctor.api.client import NetworkSnapshot, UniFiClient

console = Console()


def _build_ap_table(snapshot: NetworkSnapshot) -> Table:
    table = Table(title="Access Points", show_header=True, header_style="bold cyan")
    table.add_column("AP", style="cyan")
    table.add_column("Clients", justify="right")
    table.add_column("2.4G Ch")
    table.add_column("2.4G Util", justify="right")
    table.add_column("5G Ch")
    table.add_column("5G Util", justify="right")
    table.add_column("Satisfaction", justify="right")

    for ap in snapshot.aps:
        clients = snapshot.clients_for_ap(ap.mac)
        n_wireless = len([c for c in clients if not c.is_wired])

        ch_2g, util_2g, ch_5g, util_5g = "-", "-", "-", "-"
        for rs in ap.radio_table_stats:
            try:
                ch_int = int(rs.channel)
            except (ValueError, TypeError):
                continue
            if 0 < ch_int <= 14:
                ch_2g = str(ch_int)
                cu = rs.cu_total
                color = "green" if cu < 30 else "yellow" if cu < 50 else "red"
                util_2g = f"[{color}]{cu}%[/{color}]"
            elif ch_int > 14:
                ch_5g = str(ch_int)
                cu = rs.cu_total
                color = "green" if cu < 30 else "yellow" if cu < 50 else "red"
                util_5g = f"[{color}]{cu}%[/{color}]"

        sat = ap.satisfaction
        sat_style = "green" if sat >= 80 else "yellow" if sat >= 50 else "red"

        table.add_row(
            ap.display_name,
            str(n_wireless),
            ch_2g,
            util_2g,
            ch_5g,
            util_5g,
            f"[{sat_style}]{sat}%[/{sat_style}]",
        )
    return table


def _build_client_summary(snapshot: NetworkSnapshot) -> Table:
    table = Table(title="Client Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    wireless = [c for c in snapshot.clients if not c.is_wired]
    wired = [c for c in snapshot.clients if c.is_wired]
    on_5g = [c for c in wireless if c.is_5g]
    on_2g = [c for c in wireless if c.is_2g]
    poor_signal = [c for c in wireless if (c.rssi or c.signal or 0) < -72 and (c.rssi or c.signal or 0) != 0]

    table.add_row("Total Wireless", str(len(wireless)))
    table.add_row("Total Wired", str(len(wired)))
    table.add_row("On 5 GHz", f"[green]{len(on_5g)}[/green]")
    table.add_row("On 2.4 GHz", f"[yellow]{len(on_2g)}[/yellow]")
    table.add_row("Poor Signal (<-72 dBm)", f"[red]{len(poor_signal)}[/red]" if poor_signal else "[green]0[/green]")

    return table


def _build_events_panel(snapshot: NetworkSnapshot) -> Panel:
    recent = sorted(snapshot.events, key=lambda e: e.time, reverse=True)[:10]
    lines = []
    for e in recent:
        ts = e.timestamp.strftime("%H:%M:%S") if e.time else "??:??:??"
        msg = e.msg or e.key
        if len(msg) > 80:
            msg = msg[:77] + "..."
        lines.append(f"[dim]{ts}[/dim] {msg}")

    content = "\n".join(lines) if lines else "[dim]No recent events[/dim]"
    return Panel(content, title="Recent Events", border_style="dim")


def _build_health_panel(snapshot: NetworkSnapshot) -> Panel:
    lines = []
    for h in snapshot.health:
        status = h.status
        style = "green" if status == "ok" else "yellow" if status == "warn" else "red"
        lines.append(f"[{style}]● {h.subsystem}: {status}[/{style}]")

        if h.subsystem == "wan" and h.latency:
            lines.append(f"  WAN latency: {h.latency}ms")
        if h.subsystem == "wlan":
            lines.append(f"  APs: {h.num_ap}  Clients: {h.num_sta}")

    content = "\n".join(lines) if lines else "[dim]No health data[/dim]"
    return Panel(content, title="Network Health", border_style="cyan")


async def run_watch(client: UniFiClient, interval: int = 5) -> None:
    """Run a live-updating dashboard."""
    console.print("[bold cyan]UniFi Doctor — Live Dashboard[/bold cyan]")
    console.print(f"[dim]Refreshing every {interval}s. Press Ctrl+C to stop.[/dim]\n")

    with Live(console=console, refresh_per_second=1) as live:
        try:
            while True:
                snapshot = await client.fetch_all()

                layout = Layout()
                layout.split_column(
                    Layout(name="header", size=3),
                    Layout(name="body"),
                    Layout(name="footer", size=14),
                )

                layout["header"].update(
                    Panel(
                        f"[bold]UniFi Doctor — Live Dashboard[/bold]  |  "
                        f"Last refresh: {datetime.now().strftime('%H:%M:%S')}  |  "
                        f"APs: {len(snapshot.aps)}  Clients: {len(snapshot.clients)}",
                        border_style="cyan",
                    )
                )

                layout["body"].split_row(
                    Layout(_build_ap_table(snapshot), name="aps"),
                    Layout(name="right"),
                )
                layout["body"]["right"].split_column(
                    Layout(_build_client_summary(snapshot)),
                    Layout(_build_health_panel(snapshot)),
                )

                layout["footer"].update(_build_events_panel(snapshot))

                live.update(layout)
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/dim]")
