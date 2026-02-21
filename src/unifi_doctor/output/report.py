"""Rich terminal report formatting."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from unifi_doctor.analysis.rules import normalize_rate_mbps
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import (
    ChannelPlan,
    ClientInfo,
    DeviceInfo,
    DiagnosticReport,
    Finding,
    Severity,
)

console = Console()

SEVERITY_STYLES = {
    Severity.CRITICAL: ("bold red", "🔴 CRITICAL"),
    Severity.WARNING: ("bold yellow", "🟠 WARNING"),
    Severity.INFO: ("bold blue", "🟡 INFO"),
    Severity.GOOD: ("bold green", "🟢 GOOD"),
}


def print_report(report: DiagnosticReport) -> None:
    """Print the full diagnostic report with Rich formatting."""
    console.print()
    console.print(
        Panel(
            f"[bold]UniFi Doctor — Diagnostic Report[/bold]\n"
            f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Modules: {', '.join(report.modules_run)}",
            border_style="cyan",
        )
    )

    # Summary counts
    counts = {
        Severity.CRITICAL: len(report.critical),
        Severity.WARNING: len(report.warnings),
        Severity.INFO: len(report.info),
        Severity.GOOD: len(report.good),
    }

    summary = Table(show_header=False, box=None, padding=(0, 2))
    for sev, count in counts.items():
        style, label = SEVERITY_STYLES[sev]
        suffix = ""
        if sev == Severity.CRITICAL and count > 0:
            suffix = " — fix these first, they're probably causing your streaming failures"
        elif sev == Severity.WARNING and count > 0:
            suffix = " — these degrade performance"
        elif sev == Severity.INFO and count > 0:
            suffix = " — optimizations"
        elif sev == Severity.GOOD and count > 0:
            suffix = " — configured correctly"
        summary.add_row(
            Text(f"{label} — {count} issue{'s' if count != 1 else ''}", style=style),
            Text(suffix, style="dim"),
        )
    console.print(summary)
    console.print()

    # Print findings grouped by severity
    for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO, Severity.GOOD]:
        findings = [f for f in report.findings if f.severity == severity]
        if not findings:
            continue

        style, label = SEVERITY_STYLES[severity]
        console.print(f"\n[{style}]{'═' * 60}[/{style}]")
        console.print(f"[{style}]{label}[/{style}]")
        console.print(f"[{style}]{'═' * 60}[/{style}]")

        for finding in findings:
            _print_finding(finding)

    # Channel plan
    if report.channel_plan:
        print_channel_plan(report.channel_plan)


def _print_finding(finding: Finding) -> None:
    """Print a single finding."""
    style, label = SEVERITY_STYLES[finding.severity]

    console.print()
    console.print(f"  [{style}]■ {finding.title}[/{style}]")
    console.print(f"    [dim]{finding.module}[/dim]")

    if finding.detail:
        for line in finding.detail.split("\n"):
            console.print(f"    {line}")

    if finding.recommendation:
        console.print(f"    [bold]→ {finding.recommendation}[/bold]")

    if finding.ui_path:
        console.print(f"    [dim]📍 {finding.ui_path}[/dim]")


def print_channel_plan(plans: list[ChannelPlan]) -> None:
    """Print the recommended channel plan as a table."""
    console.print()
    console.print(Panel("[bold]Recommended Channel Plan[/bold]", border_style="cyan"))

    table = Table(show_header=True, header_style="bold")
    table.add_column("AP", style="cyan")
    table.add_column("Band")
    table.add_column("Current Ch")
    table.add_column("→ Recommended Ch", style="bold green")
    table.add_column("Current Width")
    table.add_column("→ Width", style="bold green")
    table.add_column("Current Power")
    table.add_column("→ Power", style="bold green")
    table.add_column("Reason", style="dim")

    for plan in plans:
        ch_style = "green" if str(plan.current_channel) == str(plan.recommended_channel) else "yellow"
        w_style = "green" if plan.current_width == plan.recommended_width else "yellow"
        p_style = "green" if plan.current_power == plan.recommended_power else "yellow"

        table.add_row(
            plan.ap_name,
            plan.band.value.upper(),
            str(plan.current_channel),
            f"[{ch_style}]{plan.recommended_channel}[/{ch_style}]",
            f"{plan.current_width} MHz",
            f"[{w_style}]{plan.recommended_width} MHz[/{w_style}]",
            plan.current_power,
            f"[{p_style}]{plan.recommended_power}[/{p_style}]",
            plan.reason,
        )

    console.print(table)


def print_clients_table(clients: list[ClientInfo], aps: list[DeviceInfo]) -> None:
    """Print a table of all connected clients."""
    ap_lookup = {a.mac: a.display_name for a in aps}

    table = Table(show_header=True, header_style="bold", title="Connected Clients")
    table.add_column("Client", style="cyan")
    table.add_column("IP")
    table.add_column("AP", style="green")
    table.add_column("Band")
    table.add_column("Ch")
    table.add_column("Signal", justify="right")
    table.add_column("TX Rate", justify="right")
    table.add_column("RX Rate", justify="right")
    table.add_column("Proto")
    table.add_column("Satisfaction", justify="right")

    wireless = sorted(
        [c for c in clients if not c.is_wired],
        key=lambda c: c.rssi or c.signal or 0,
    )

    for c in wireless:
        rssi = c.rssi or c.signal
        signal_style = "green"
        if rssi and rssi < -72:
            signal_style = "red"
        elif rssi and rssi < -65:
            signal_style = "yellow"

        band = "5G" if c.is_5g else "2.4G" if c.is_2g else "?"
        band_style = "green" if c.is_5g else "yellow"

        tx = normalize_rate_mbps(c.tx_rate)
        rx = normalize_rate_mbps(c.rx_rate)

        sat = c.satisfaction
        sat_style = "green" if sat >= 80 else "yellow" if sat >= 50 else "red"

        table.add_row(
            c.display_name,
            c.ip,
            ap_lookup.get(c.ap_mac, c.ap_mac[:8]),
            f"[{band_style}]{band}[/{band_style}]",
            str(c.channel),
            f"[{signal_style}]{rssi} dBm[/{signal_style}]" if rssi else "-",
            f"{tx} Mbps" if tx else "-",
            f"{rx} Mbps" if rx else "-",
            c.radio_proto or "-",
            f"[{sat_style}]{sat}%[/{sat_style}]",
        )

    # Wired clients
    wired = [c for c in clients if c.is_wired]
    for c in wired:
        table.add_row(
            c.display_name,
            c.ip,
            ap_lookup.get(c.ap_mac, "wired"),
            "[dim]wired[/dim]",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
        )

    console.print(table)
    console.print(f"\n[dim]Total: {len(wireless)} wireless, {len(wired)} wired[/dim]")


def print_aps_table(aps: list[DeviceInfo], snapshot: NetworkSnapshot) -> None:
    """Print a table of all APs with radio info."""
    table = Table(show_header=True, header_style="bold", title="Access Points")
    table.add_column("AP", style="cyan")
    table.add_column("Model")
    table.add_column("IP")
    table.add_column("Clients", justify="right")
    table.add_column("2.4G Ch")
    table.add_column("2.4G Util", justify="right")
    table.add_column("5G Ch")
    table.add_column("5G Util", justify="right")
    table.add_column("Uplink")
    table.add_column("Satisfaction", justify="right")

    for ap in aps:
        clients = snapshot.clients_for_ap(ap.mac)
        n_clients = len([c for c in clients if not c.is_wired])

        # Extract radio info
        ch_2g, util_2g, ch_5g, util_5g = "-", "-", "-", "-"
        for rs in ap.radio_table_stats:
            ch = rs.channel
            try:
                ch_int = int(ch)
            except (ValueError, TypeError):
                continue
            if 0 < ch_int <= 14:
                ch_2g = str(ch_int)
                util_2g = f"{rs.cu_total}%"
            elif ch_int > 14:
                ch_5g = str(ch_int)
                util_5g = f"{rs.cu_total}%"

        # Uplink
        uplink_str = "wired"
        if ap.uplink_type == "wireless" or (ap.uplink and ap.uplink.type == "wireless"):
            uplink_str = "[red]MESH[/red]"
        elif ap.uplink and ap.uplink.speed:
            speed = ap.uplink.speed
            if speed < 1000:
                uplink_str = f"[yellow]{speed} Mbps[/yellow]"
            else:
                uplink_str = f"[green]{speed} Mbps[/green]"

        sat = ap.satisfaction
        sat_style = "green" if sat >= 80 else "yellow" if sat >= 50 else "red"

        table.add_row(
            ap.display_name,
            ap.model,
            ap.ip,
            str(n_clients),
            ch_2g,
            util_2g,
            ch_5g,
            util_5g,
            uplink_str,
            f"[{sat_style}]{sat}%[/{sat_style}]",
        )

    console.print(table)
