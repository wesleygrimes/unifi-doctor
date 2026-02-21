"""Tests for analysis modules using mock data."""

from tests.conftest import make_ap, make_client, make_snapshot, make_wlan
from unifi_doctor.analysis import rf, roaming, settings, streaming, throughput
from unifi_doctor.models.types import (
    Severity,
    SiteSetting,
    Topology,
)


def test_rf_duplicate_5g_channels():
    ap1 = make_ap(mac="aa:bb:cc:dd:ee:01", name="AP-1", ch_5g=36)
    ap2 = make_ap(mac="aa:bb:cc:dd:ee:02", name="AP-2", ch_5g=36)
    snap = make_snapshot(devices=[ap1, ap2])
    findings, plan = rf.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert len(critical) >= 1
    assert any("channel 36" in f.title.lower() for f in critical)


def test_rf_invalid_24g_channel():
    ap = make_ap(ch_2g=3)
    snap = make_snapshot(devices=[ap])
    findings, _ = rf.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("invalid" in f.title.lower() and "channel 3" in f.title.lower() for f in warnings)


def test_settings_ids_ips_critical():
    snap = make_snapshot(
        settings=[SiteSetting(key="ips", ips_mode="ips")],
    )
    findings = settings.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert len(critical) >= 1
    assert any("ids/ips" in f.title.lower() for f in critical)


def test_settings_sqm_critical():
    snap = make_snapshot(
        settings=[SiteSetting(key="sqm", sqm_enabled=True)],
    )
    findings = settings.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("smart queues" in f.title.lower() for f in critical)


def test_throughput_mesh_critical():
    ap = make_ap()
    ap.uplink_type = "wireless"
    snap = make_snapshot(devices=[ap])
    findings = throughput.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("mesh" in f.title.lower() for f in critical)


def test_roaming_fast_roaming_disabled():
    wlan = make_wlan(name="HomeNet", fast_roaming_enabled=False)
    ap = make_ap()
    snap = make_snapshot(devices=[ap], wlan_configs=[wlan])
    findings = roaming.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("802.11r" in f.title for f in warnings)


def test_streaming_device_detection():
    # Amazon Fire TV OUI
    client = make_client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-55,
        tx_rate=300000,
        rx_rate=300000,
    )
    ap = make_ap()
    snap = make_snapshot(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    info = [f for f in findings if f.severity == Severity.INFO]
    assert any("streaming device" in f.title.lower() for f in info)


def test_streaming_weak_signal_critical():
    client = make_client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-80,
        tx_rate=50000,
        rx_rate=50000,
    )
    ap = make_ap()
    snap = make_snapshot(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("weak signal" in f.title.lower() or "phy rate" in f.title.lower() for f in critical)
