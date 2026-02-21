"""Edge-case tests for all analysis modules."""

from __future__ import annotations

from unifi_doctor.analysis import rf, roaming, rules, settings, streaming, throughput
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import (
    ClientInfo,
    DeviceInfo,
    PortTableEntry,
    RadioTableEntry,
    RadioTableStatsEntry,
    Severity,
    SiteSetting,
    Topology,
    UplinkInfo,
    WLANConfig,
)

# ---------------------------------------------------------------------------
# Inline helpers — no dependency on conftest.py
# ---------------------------------------------------------------------------


def _snap(
    devices=None,
    clients=None,
    rogue_aps=None,
    wlan_configs=None,
    settings_list=None,
    health=None,
    events=None,
):
    return NetworkSnapshot(
        devices=devices or [],
        clients=clients or [],
        rogue_aps=rogue_aps or [],
        wlan_configs=wlan_configs or [],
        settings=settings_list or [],
        health=health or [],
        events=events or [],
    )


def _ap(
    mac="aa:bb:cc:dd:ee:01",
    name="Test-AP",
    ch_2g=1,
    ch_5g=36,
    ht_2g=20,
    ht_5g=40,
    power_2g="medium",
    cu_2g=10,
    cu_5g=15,
    nf_2g=-100,
    nf_5g=-100,
    uplink_speed=1000,
    port_table=None,
) -> DeviceInfo:
    return DeviceInfo(
        mac=mac,
        name=name,
        type="uap",
        model="U6-LR",
        radio_table=[
            RadioTableEntry(radio="ng", channel=ch_2g, ht=ht_2g, tx_power_mode=power_2g),
            RadioTableEntry(radio="na", channel=ch_5g, ht=ht_5g, tx_power_mode="medium"),
        ],
        radio_table_stats=[
            RadioTableStatsEntry(name="ra0", channel=ch_2g, cu_total=cu_2g, noise_floor=nf_2g),
            RadioTableStatsEntry(name="rai0", channel=ch_5g, cu_total=cu_5g, noise_floor=nf_5g),
        ],
        uplink=UplinkInfo(type="wire", speed=uplink_speed),
        port_table=port_table or [],
    )


def _client(
    mac="cc:dd:ee:ff:00:01",
    hostname="test-client",
    name="",
    ap_mac="aa:bb:cc:dd:ee:01",
    channel=36,
    rssi=-55,
    tx_rate=300000,
    rx_rate=300000,
    is_wired=False,
    radio_proto="ax",
    oui="",
) -> ClientInfo:
    return ClientInfo(
        mac=mac,
        hostname=hostname,
        name=name,
        ap_mac=ap_mac,
        channel=channel,
        rssi=rssi,
        tx_rate=tx_rate,
        rx_rate=rx_rate,
        is_wired=is_wired,
        radio_proto=radio_proto,
        oui=oui,
    )


def _gateway(mac="aa:bb:cc:dd:ee:ff", version="7.1.0") -> DeviceInfo:
    return DeviceInfo(mac=mac, name="UDM-Pro", type="udm", model="UDM-Pro", version=version)


def _wlan(
    name="TestNet",
    enabled=True,
    fast_roaming_enabled=True,
    bss_transition=True,
    rrm_enabled=True,
    band_steering_mode="prefer_5g",
    multicast_enhance=True,
    igmp_snooping=True,
    dtim_na=1,
    dtim_ng=1,
    pmf_mode="disabled",
) -> WLANConfig:
    return WLANConfig(
        name=name,
        enabled=enabled,
        fast_roaming_enabled=fast_roaming_enabled,
        bss_transition=bss_transition,
        rrm_enabled=rrm_enabled,
        band_steering_mode=band_steering_mode,
        multicast_enhance=multicast_enhance,
        igmp_snooping=igmp_snooping,
        dtim_na=dtim_na,
        dtim_ng=dtim_ng,
        pmf_mode=pmf_mode,
    )


# ===================================================================
# RF edge cases
# ===================================================================


def test_rf_empty_snapshot_returns_no_aps_warning_and_empty_plan():
    """Empty snapshot -> warning 'No APs found' + empty channel plan."""
    snap = _snap()
    findings, plan = rf.analyze(snap, Topology())
    assert len(plan) == 0
    assert any(f.severity == Severity.WARNING and "No APs found" in f.title for f in findings)


def test_rf_single_ap_no_duplicate_channel_findings_and_generates_plan():
    """Single AP should never produce duplicate-channel findings and should still generate a channel plan."""
    ap = _ap(ch_5g=36)
    snap = _snap(devices=[ap])
    findings, plan = rf.analyze(snap, Topology())

    # No critical duplicate-channel findings
    dup_findings = [f for f in findings if "shared by" in f.title.lower()]
    assert len(dup_findings) == 0

    # Channel plan should have entries (2g + 5g)
    assert len(plan) >= 2


def test_rf_high_channel_utilization_generates_warning():
    """Channel utilization > 50% should produce a warning."""
    ap = _ap(cu_2g=60)
    snap = _snap(devices=[ap])
    findings, _ = rf.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("channel utilization" in f.title.lower() and "60%" in f.title for f in warnings)


def test_rf_high_noise_floor_generates_warning():
    """Noise floor above -90 dBm should produce a warning."""
    ap = _ap(nf_2g=-85)
    snap = _snap(devices=[ap])
    findings, _ = rf.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("noise floor" in f.title.lower() and "-85" in f.title for f in warnings)


def test_rf_24g_width_above_20_generates_warning():
    """2.4 GHz width > 20 MHz should produce a warning."""
    ap = _ap(ht_2g=40)
    snap = _snap(devices=[ap])
    findings, _ = rf.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("2.4 ghz width" in f.title.lower() and "40" in f.title for f in warnings)


def test_rf_24g_power_high_generates_warning():
    """2.4 GHz power set to 'high' should produce a warning."""
    ap = _ap(power_2g="high")
    snap = _snap(devices=[ap])
    findings, _ = rf.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("power" in f.title.lower() and "too high" in f.title.lower() for f in warnings)


# ===================================================================
# Settings edge cases
# ===================================================================


def test_settings_dpi_enabled_generates_warning():
    """DPI enabled should produce a warning."""
    snap = _snap(settings_list=[SiteSetting(key="dpi", dpi_enabled=True)])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("dpi" in f.title.lower() for f in warnings)


def test_settings_buggy_firmware_generates_warning():
    """Firmware version '6.5.28' should produce a warning."""
    gw = _gateway(version="6.5.28")
    snap = _snap(devices=[gw])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("firmware" in f.title.lower() and "6.5.28" in f.title for f in warnings)


def test_settings_pmf_required_generates_info():
    """PMF mode 'required' should produce an info finding."""
    wlan = _wlan(pmf_mode="required")
    snap = _snap(wlan_configs=[wlan])
    findings = settings.analyze(snap, Topology())
    infos = [f for f in findings if f.severity == Severity.INFO]
    assert any("pmf" in f.title.lower() and "required" in f.title.lower() for f in infos)


def test_settings_auto_optimize_enabled_generates_warning():
    """Auto-optimize enabled should produce a warning."""
    snap = _snap(settings_list=[SiteSetting(key="auto_optimize", auto_optimize_enabled=True)])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("auto-optimize" in f.title.lower() for f in warnings)


def test_settings_multicast_enhancement_off_generates_warning():
    """Multicast enhancement off should produce a warning."""
    wlan = _wlan(multicast_enhance=False)
    snap = _snap(wlan_configs=[wlan])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("multicast enhancement" in f.title.lower() for f in warnings)


def test_settings_igmp_snooping_off_generates_warning():
    """IGMP snooping off should produce a warning."""
    wlan = _wlan(igmp_snooping=False)
    snap = _snap(wlan_configs=[wlan])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("igmp snooping" in f.title.lower() for f in warnings)


def test_settings_dtim_above_1_generates_warning():
    """DTIM interval > 1 should produce a warning."""
    wlan = _wlan(dtim_na=3, dtim_ng=3)
    snap = _snap(wlan_configs=[wlan])
    findings = settings.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("dtim" in f.title.lower() for f in warnings)


# ===================================================================
# Roaming edge cases
# ===================================================================


def test_roaming_no_aps_returns_empty():
    """No APs should return an empty list."""
    snap = _snap()
    findings = roaming.analyze(snap, Topology())
    assert findings == []


def test_roaming_sticky_client_generates_warning():
    """Client with RSSI < -72 and APs present should produce a warning."""
    ap = _ap()
    client = _client(rssi=-78, channel=36)
    snap = _snap(devices=[ap], clients=[client])
    findings = roaming.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("sticky client" in f.title.lower() for f in warnings)


def test_roaming_band_steering_force_5g_generates_warning():
    """Band steering 'force_5g' should produce a warning."""
    ap = _ap()
    wlan = _wlan(band_steering_mode="force_5g")
    snap = _snap(devices=[ap], wlan_configs=[wlan])
    findings = roaming.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("force" in f.title.lower() and "band steering" in f.title.lower() for f in warnings)


def test_roaming_band_steering_prefer_5g_generates_good():
    """Band steering 'prefer_5g' should produce a GOOD finding."""
    ap = _ap()
    wlan = _wlan(band_steering_mode="prefer_5g")
    snap = _snap(devices=[ap], wlan_configs=[wlan])
    findings = roaming.analyze(snap, Topology())
    good = [f for f in findings if f.severity == Severity.GOOD]
    assert any("band steering" in f.title.lower() and "prefer 5g" in f.title.lower() for f in good)


def test_roaming_band_steering_off_generates_info():
    """Band steering 'off' should produce an INFO finding."""
    ap = _ap()
    wlan = _wlan(band_steering_mode="off")
    snap = _snap(devices=[ap], wlan_configs=[wlan])
    findings = roaming.analyze(snap, Topology())
    infos = [f for f in findings if f.severity == Severity.INFO]
    assert any("band steering" in f.title.lower() and "off" in f.title.lower() for f in infos)


# ===================================================================
# Throughput edge cases
# ===================================================================


def test_throughput_legacy_device_generates_warning():
    """Client with radio_proto='b' should produce a legacy device warning."""
    client = _client(radio_proto="b", channel=6, rssi=-55, tx_rate=11000, rx_rate=11000)
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = throughput.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("legacy" in f.title.lower() and "802.11b" in f.title.lower() for f in warnings)


def test_throughput_5g_poor_rate_generates_warning():
    """5 GHz client with PHY rate < 100 Mbps should produce a warning."""
    client = _client(channel=36, tx_rate=50, rx_rate=50, radio_proto="ac")
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = throughput.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("phy rate" in f.title.lower() for f in warnings)


def test_throughput_slow_uplink_generates_warning():
    """AP with 100 Mbps uplink should produce a warning."""
    ap = _ap(uplink_speed=100)
    snap = _snap(devices=[ap])
    findings = throughput.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("uplink" in f.title.lower() and "100" in f.title for f in warnings)


def test_throughput_port_errors_generates_warning():
    """Port with > 100 errors should produce a warning."""
    port = PortTableEntry(port_idx=1, up=True, rx_errors=150, tx_errors=50)
    ap = _ap(port_table=[port])
    snap = _snap(devices=[ap])
    findings = throughput.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("error" in f.title.lower() for f in warnings)


def test_throughput_all_wired_no_phy_rate_findings():
    """All wired clients should produce no PHY rate warnings."""
    client = _client(is_wired=True, channel=0, rssi=0, tx_rate=0, rx_rate=0)
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = throughput.analyze(snap, Topology())
    phy_findings = [f for f in findings if "phy rate" in f.title.lower()]
    assert len(phy_findings) == 0


# ===================================================================
# Streaming edge cases
# ===================================================================


def test_streaming_device_on_24g_generates_critical():
    """Streaming device on 2.4 GHz (channel 6) should produce a CRITICAL."""
    client = _client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=6,
        rssi=-55,
        tx_rate=72000,
        rx_rate=72000,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("2.4 ghz" in f.title.lower() for f in critical)


def test_streaming_device_good_signal_5g_generates_good():
    """Streaming device with good signal on 5 GHz should produce GOOD findings."""
    client = _client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-50,
        tx_rate=300000,
        rx_rate=300000,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    good = [f for f in findings if f.severity == Severity.GOOD]
    # Should have good signal finding and good band finding
    assert any("good signal" in f.title.lower() for f in good)
    assert any("5 ghz" in f.title.lower() for f in good)


def test_streaming_device_marginal_signal_generates_warning():
    """Streaming device with marginal signal (-68 dBm) should produce a WARNING."""
    client = _client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-68,
        tx_rate=200000,
        rx_rate=200000,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    assert any("marginal signal" in f.title.lower() for f in warnings)


def test_streaming_no_devices_generates_info():
    """No streaming devices should produce an INFO about no devices found."""
    client = _client(
        mac="00:11:22:33:44:55",
        hostname="laptop",
        channel=36,
        rssi=-55,
        tx_rate=300000,
        rx_rate=300000,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    infos = [f for f in findings if f.severity == Severity.INFO]
    assert any("no streaming devices" in f.title.lower() for f in infos)


def test_streaming_rate_normalization_kbps_to_mbps():
    """tx_rate=300000 (Kbps) should normalize to 300 Mbps and not trigger critical PHY rate alert."""
    client = _client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-50,
        tx_rate=300000,
        rx_rate=300000,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    # Should NOT have a critical or warning about PHY rate (300 Mbps is fine)
    phy_findings = [f for f in findings if "phy rate" in f.title.lower()]
    assert all(f.severity not in (Severity.CRITICAL, Severity.WARNING) for f in phy_findings)


def test_streaming_device_low_phy_rate_generates_critical():
    """Streaming device with very low PHY rate should produce a CRITICAL."""
    client = _client(
        mac="F0:D2:F1:AA:BB:CC",
        hostname="fire-tv",
        channel=36,
        rssi=-50,
        tx_rate=30,
        rx_rate=30,
    )
    ap = _ap()
    snap = _snap(devices=[ap], clients=[client])
    findings = streaming.analyze(snap, Topology())
    critical = [f for f in findings if f.severity == Severity.CRITICAL]
    assert any("phy rate" in f.title.lower() for f in critical)


# ===================================================================
# Rate normalization (rules module)
# ===================================================================


def test_normalize_rate_mbps_above_10000():
    """Values above 10000 should be divided by 1000 (Kbps -> Mbps)."""
    assert rules.normalize_rate_mbps(300000) == 300
    assert rules.normalize_rate_mbps(10001) == 10


def test_normalize_rate_mbps_below_or_equal_10000():
    """Values <= 10000 should be returned as-is (already Mbps)."""
    assert rules.normalize_rate_mbps(300) == 300
    assert rules.normalize_rate_mbps(10000) == 10000
    assert rules.normalize_rate_mbps(0) == 0
