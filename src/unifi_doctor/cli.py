"""CLI entry points for unifi-doctor."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt

from unifi_doctor.api.client import (
    Config,
    ControllerConfig,
    NetworkSnapshot,
    UniFiClient,
    load_config,
    load_topology,
    save_config,
)
from unifi_doctor.models.types import DiagnosticReport, Topology

app = typer.Typer(
    name="unifi-doctor",
    help="Opinionated UniFi network diagnostic tool for UDM Pro.",
    no_args_is_help=True,
)
console = Console()

# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------


def _get_client(verify_ssl: bool = False, verbose: bool = False) -> UniFiClient:
    cfg = load_config()
    if not cfg.controller.password:
        console.print("[red]No credentials configured. Run 'unifi-doctor setup' first.[/red]")
        raise typer.Exit(1)
    return UniFiClient(cfg, verify_ssl=verify_ssl, verbose=verbose)


def _run_async(coro):
    """Run an async coroutine, handling event loop creation."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an async context — shouldn't happen in CLI, but handle it
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


async def _fetch_snapshot(client: UniFiClient) -> NetworkSnapshot:
    """Fetch all data with a progress indicator."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting and fetching data from controller...", total=None)
        async with client:
            snapshot = await client.fetch_all()
        progress.update(task, description=f"Done — {len(snapshot.devices)} devices, {len(snapshot.clients)} clients")
    return snapshot


def _run_analysis(
    snapshot: NetworkSnapshot,
    topology: Topology,
    modules: list[str] | None = None,
) -> DiagnosticReport:
    """Run analysis modules and return a report."""
    from unifi_doctor.analysis import rf, roaming, settings, streaming, throughput

    all_modules = {
        "rf": rf,
        "roaming": roaming,
        "throughput": throughput,
        "settings": settings,
        "streaming": streaming,
    }

    if modules:
        selected = {k: v for k, v in all_modules.items() if k in modules}
    else:
        selected = all_modules

    report = DiagnosticReport(modules_run=list(selected.keys()))

    for name, mod in selected.items():
        console.print(f"[dim]Running {name} analysis...[/dim]")
        if name == "rf":
            findings, channel_plan = mod.analyze(snapshot, topology)
            report.findings.extend(findings)
            report.channel_plan.extend(channel_plan)
        else:
            findings = mod.analyze(snapshot, topology)
            report.findings.extend(findings)

    return report


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def setup(
    verify_ssl: bool = typer.Option(False, "--verify-ssl", help="Verify SSL certificates"),
):
    """First-run setup: configure controller connection and map AP topology."""
    from unifi_doctor.topology.interview import run_interview

    console.print("[bold cyan]UniFi Doctor — Setup[/bold cyan]\n")

    # Controller config
    existing = load_config()
    host = Prompt.ask("Controller URL", default=existing.controller.host)
    username = Prompt.ask("Username", default=existing.controller.username)
    password = Prompt.ask("Password (hidden)", password=True, default="")

    if not password and existing.controller.password:
        password = existing.controller.password

    site = Prompt.ask("Site name", default=existing.controller.site)

    cfg = Config(
        controller=ControllerConfig(
            host=host,
            username=username,
            password=password,
            site=site,
            verify_ssl=verify_ssl,
        )
    )
    save_config(cfg)
    console.print("[green]Config saved to ~/.unifi-doctor/config.yaml[/green]\n")

    # Test connection and discover APs
    client = UniFiClient(cfg, verify_ssl=verify_ssl)

    async def _discover():
        async with client:
            devices = await client.get_devices()
            aps = [d for d in devices if d.is_ap]
            return aps, devices

    try:
        aps, devices = _run_async(_discover())
        run_interview(aps, devices)
    except Exception as e:
        console.print(f"[red]Failed to connect: {e}[/red]")
        console.print("[yellow]Config saved — fix connection and re-run setup.[/yellow]")


@app.command()
def scan(
    module: str | None = typer.Option(
        None,
        "--module",
        "-m",
        help="Run a specific module: rf, roaming, throughput, settings, streaming",
    ),
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Run diagnostic scan (all modules or a specific one)."""
    from unifi_doctor.output.report import print_report

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)
    topology = load_topology()

    modules = [module] if module else None

    snapshot = _run_async(_fetch_snapshot(client))
    report = _run_analysis(snapshot, topology, modules)

    if output_json:
        data = report.model_dump(mode="json")
        console.print_json(json.dumps(data, indent=2, default=str))
    else:
        print_report(report)


@app.command()
def clients(
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json"),
):
    """List all connected clients with AP, signal, and rates."""
    from unifi_doctor.output.report import print_clients_table

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)
    snapshot = _run_async(_fetch_snapshot(client))

    if output_json:
        data = [c.model_dump(mode="json") for c in snapshot.clients]
        console.print_json(json.dumps(data, indent=2, default=str))
    else:
        print_clients_table(snapshot.clients, snapshot.aps)


@app.command()
def aps(
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json"),
):
    """List all APs with channels, power, and utilization."""
    from unifi_doctor.output.report import print_aps_table

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)

    snapshot = _run_async(_fetch_snapshot(client))

    if output_json:
        data = [d.model_dump(mode="json") for d in snapshot.aps]
        console.print_json(json.dumps(data, indent=2, default=str))
    else:
        print_aps_table(snapshot.aps, snapshot)


@app.command()
def channels(
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json"),
):
    """Show current vs recommended channel plan."""
    from unifi_doctor.analysis import rf
    from unifi_doctor.output.report import print_channel_plan

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)
    topology = load_topology()
    snapshot = _run_async(_fetch_snapshot(client))
    _, channel_plan = rf.analyze(snapshot, topology)

    if output_json:
        data = [p.model_dump(mode="json") for p in channel_plan]
        console.print_json(json.dumps(data, indent=2, default=str))
    else:
        print_channel_plan(channel_plan)


@app.command(name="apply-plan")
def apply_plan(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Apply recommended channel/power changes via API."""
    from unifi_doctor.analysis import rf

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)
    topology = load_topology()

    async def _apply():
        snapshot = await _fetch_snapshot(client)
        _, channel_plan = rf.analyze(snapshot, topology)

        if not channel_plan:
            console.print("[yellow]No channel plan to apply.[/yellow]")
            return

        changes: list[dict] = []
        for plan in channel_plan:
            needs_change = (
                str(plan.current_channel) != str(plan.recommended_channel)
                or plan.current_width != plan.recommended_width
            )
            if needs_change:
                changes.append(
                    {
                        "ap_mac": plan.ap_mac,
                        "ap_name": plan.ap_name,
                        "band": plan.band.value,
                        "channel": plan.recommended_channel,
                        "width": plan.recommended_width,
                    }
                )

        if not changes:
            console.print("[green]All channels already match the recommended plan.[/green]")
            return

        console.print(f"\n[bold]{'DRY RUN — ' if dry_run else ''}Changes to apply:[/bold]\n")
        for ch in changes:
            console.print(
                f"  [cyan]{ch['ap_name']}[/cyan] {ch['band'].upper()}: "
                f"channel → {ch['channel']}, width → {ch['width']} MHz"
            )

        if dry_run:
            console.print("\n[yellow]Dry run — no changes applied.[/yellow]")
            return

        confirm = Prompt.ask("\nApply these changes?", choices=["yes", "no"], default="no")
        if confirm != "yes":
            console.print("[yellow]Cancelled.[/yellow]")
            return

        async with client:
            for ch in changes:
                radio_band = "ng" if ch["band"] == "2g" else "na"
                # Build the radio override payload
                payload = {
                    "radio_table": [
                        {
                            "radio": radio_band,
                            "channel": ch["channel"],
                            "ht": ch["width"],
                        }
                    ]
                }
                console.print(f"  Applying to {ch['ap_name']} ({radio_band})...")
                # Use set-inform or force-provision
                success = await client.send_device_command(
                    ch["ap_mac"],
                    "set-radiotable",
                    payload,
                )
                if success:
                    console.print("  [green]✓ Applied[/green]")
                else:
                    console.print("  [yellow]⚠ May need manual application via UI[/yellow]")

        console.print("\n[green]Done. APs may take 30-60s to apply new radio settings.[/green]")

    _run_async(_apply())


@app.command()
def watch(
    interval: int = typer.Option(5, "--interval", "-i", help="Refresh interval in seconds"),
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Live dashboard — refresh every N seconds."""
    from unifi_doctor.output.dashboard import run_watch

    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)

    async def _watch():
        async with client:
            await run_watch(client, interval=interval)

    _run_async(_watch())


@app.command()
def export(
    format: str = typer.Option("json", "--format", "-f", help="Export format: json"),
    output: str = typer.Option("-", "--output", "-o", help="Output file (- for stdout)"),
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Export all collected data for external analysis."""
    client = _get_client(verify_ssl=verify_ssl, verbose=verbose)

    async def _export():
        async with client:
            return await client.get_all_raw()

    data = _run_async(_export())

    json_str = json.dumps(data, indent=2, default=str)

    if output == "-":
        console.print_json(json_str)
    else:
        Path(output).write_text(json_str)
        console.print(f"[green]Exported to {output}[/green]")


@app.command()
def topology(
    live: bool = typer.Option(False, "--live", "-l", help="Overlay live client counts per AP"),
    verify_ssl: bool = typer.Option(False, "--verify-ssl"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Show ASCII topology map of AP positions."""
    from unifi_doctor.output.topology_output import print_topology_map, topology_to_json

    topo = load_topology()

    if not topo.placements:
        console.print("[yellow]No topology configured. Run 'unifi-doctor setup' first.[/yellow]")
        raise typer.Exit(1)

    client_counts: dict[str, int] | None = None

    if live:
        client = _get_client(verify_ssl=verify_ssl, verbose=verbose)
        snapshot = _run_async(_fetch_snapshot(client))
        client_counts = {}
        for ap in snapshot.aps:
            wireless = [c for c in snapshot.clients_for_ap(ap.mac) if not c.is_wired]
            client_counts[ap.mac] = len(wireless)

    if output_json:
        data = topology_to_json(topo, client_counts=client_counts)
        console.print_json(json.dumps(data, indent=2, default=str))
    else:
        print_topology_map(topo, client_counts=client_counts)


def main():
    app()


if __name__ == "__main__":
    main()
