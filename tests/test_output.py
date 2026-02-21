"""Smoke tests for Rich output formatting."""

from __future__ import annotations

import io

from rich.console import Console

from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import (
    Band,
    ChannelPlan,
    ClientInfo,
    DeviceInfo,
    DiagnosticReport,
    Finding,
    RadioTableStatsEntry,
    Severity,
    UplinkInfo,
)
from unifi_doctor.output.report import (
    print_aps_table,
    print_channel_plan,
    print_clients_table,
    print_report,
)


def _capture_console(monkeypatch):
    """Replace the module's console with one that writes to a StringIO."""
    buf = io.StringIO()
    test_console = Console(file=buf, width=200)
    monkeypatch.setattr("unifi_doctor.output.report.console", test_console)
    return buf


# ---------------------------------------------------------------------------
# Helpers to build test data
# ---------------------------------------------------------------------------


def _make_finding(severity: Severity, title: str) -> Finding:
    return Finding(
        severity=severity,
        module="test",
        title=title,
        detail="Some detail text",
        recommendation="Fix it",
    )


def _make_ap(mac: str = "aa:bb:cc:dd:ee:01", name: str = "Office-AP") -> DeviceInfo:
    return DeviceInfo(
        mac=mac,
        name=name,
        type="uap",
        model="U6-LR",
        ip="192.168.1.10",
        satisfaction=95,
        radio_table_stats=[
            RadioTableStatsEntry(name="ra0", channel=6, cu_total=15),
            RadioTableStatsEntry(name="rai0", channel=44, cu_total=8),
        ],
        uplink=UplinkInfo(type="wire", speed=1000),
    )


def _make_client(
    mac: str = "11:22:33:44:55:01",
    hostname: str = "living-room-tv",
    channel: int = 36,
    rssi: int = -55,
    is_wired: bool = False,
    ap_mac: str = "aa:bb:cc:dd:ee:01",
) -> ClientInfo:
    return ClientInfo(
        mac=mac,
        hostname=hostname,
        channel=channel,
        rssi=rssi,
        signal=rssi,
        is_wired=is_wired,
        ap_mac=ap_mac,
        ip="192.168.1.100",
        tx_rate=866,
        rx_rate=866,
        radio_proto="ax",
        satisfaction=95,
    )


def _make_channel_plan(
    ap_name: str = "Office-AP",
    ap_mac: str = "aa:bb:cc:dd:ee:01",
) -> ChannelPlan:
    return ChannelPlan(
        ap_mac=ap_mac,
        ap_name=ap_name,
        band=Band.BAND_5G,
        current_channel=36,
        recommended_channel=44,
        current_width=80,
        recommended_width=80,
        current_power="auto",
        recommended_power="medium",
        reason="Less interference on ch 44",
    )


def _make_snapshot(devices=None, clients=None) -> NetworkSnapshot:
    return NetworkSnapshot(
        devices=devices or [],
        clients=clients or [],
        rogue_aps=[],
        wlan_configs=[],
        settings=[],
        health=[],
        events=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_print_report_with_findings(monkeypatch):
    """Report with one finding per severity renders without error."""
    buf = _capture_console(monkeypatch)

    findings = [
        _make_finding(Severity.CRITICAL, "Critical Issue Found"),
        _make_finding(Severity.WARNING, "Warning Issue Found"),
        _make_finding(Severity.INFO, "Info Issue Found"),
        _make_finding(Severity.GOOD, "Good Check Passed"),
    ]
    report = DiagnosticReport(modules_run=["test"], findings=findings)
    print_report(report)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Critical Issue Found" in output
    assert "Warning Issue Found" in output
    assert "Info Issue Found" in output
    assert "Good Check Passed" in output


def test_print_report_empty(monkeypatch):
    """Empty report renders without crashing."""
    buf = _capture_console(monkeypatch)

    report = DiagnosticReport(modules_run=["test"], findings=[])
    print_report(report)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Diagnostic Report" in output


def test_print_report_with_channel_plan(monkeypatch):
    """Report with findings and a channel plan renders without error."""
    buf = _capture_console(monkeypatch)

    findings = [_make_finding(Severity.WARNING, "Channel Conflict")]
    plans = [_make_channel_plan(ap_name="Lobby-AP")]
    report = DiagnosticReport(
        modules_run=["rf"],
        findings=findings,
        channel_plan=plans,
    )
    print_report(report)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Channel Conflict" in output
    assert "Lobby-AP" in output


def test_print_clients_table(monkeypatch):
    """Client table with wireless and wired clients renders names."""
    buf = _capture_console(monkeypatch)

    ap = _make_ap()
    clients = [
        _make_client(mac="11:22:33:44:55:01", hostname="wireless-laptop", channel=44, rssi=-60),
        _make_client(mac="11:22:33:44:55:02", hostname="wired-desktop", is_wired=True, channel=0, rssi=0),
    ]
    print_clients_table(clients, [ap])

    output = buf.getvalue()
    assert len(output) > 0
    assert "wireless-laptop" in output
    assert "wired-desktop" in output


def test_print_clients_table_empty(monkeypatch):
    """Empty client list renders without crashing."""
    buf = _capture_console(monkeypatch)

    print_clients_table([], [])

    output = buf.getvalue()
    assert len(output) > 0
    assert "Connected Clients" in output


def test_print_aps_table(monkeypatch):
    """AP table renders AP names."""
    buf = _capture_console(monkeypatch)

    aps = [
        _make_ap(mac="aa:bb:cc:dd:ee:01", name="Living-Room-AP"),
        _make_ap(mac="aa:bb:cc:dd:ee:02", name="Garage-AP"),
    ]
    clients = [
        _make_client(ap_mac="aa:bb:cc:dd:ee:01"),
        _make_client(mac="11:22:33:44:55:02", ap_mac="aa:bb:cc:dd:ee:02"),
    ]
    snapshot = _make_snapshot(devices=aps, clients=clients)

    print_aps_table(aps, snapshot)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Living-Room-AP" in output
    assert "Garage-AP" in output


def test_print_aps_table_empty(monkeypatch):
    """Empty AP list renders without crashing."""
    buf = _capture_console(monkeypatch)

    snapshot = _make_snapshot()
    print_aps_table([], snapshot)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Access Points" in output


def test_print_channel_plan(monkeypatch):
    """Channel plan table renders AP names."""
    buf = _capture_console(monkeypatch)

    plans = [
        _make_channel_plan(ap_name="Bedroom-AP"),
        _make_channel_plan(ap_name="Kitchen-AP", ap_mac="aa:bb:cc:dd:ee:03"),
    ]
    print_channel_plan(plans)

    output = buf.getvalue()
    assert len(output) > 0
    assert "Bedroom-AP" in output
    assert "Kitchen-AP" in output


def test_print_channel_plan_empty(monkeypatch):
    """Empty channel plan list renders without crashing."""
    buf = _capture_console(monkeypatch)

    print_channel_plan([])

    output = buf.getvalue()
    assert len(output) > 0
    assert "Channel Plan" in output
