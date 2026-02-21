"""Tests for the NetworkSnapshot class in unifi_doctor.api.client."""

from __future__ import annotations

from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import ClientInfo, DeviceInfo, SiteSetting

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_snapshot(
    devices: list[DeviceInfo] | None = None,
    clients: list[ClientInfo] | None = None,
    settings: list[SiteSetting] | None = None,
) -> NetworkSnapshot:
    return NetworkSnapshot(
        devices=devices or [],
        clients=clients or [],
        rogue_aps=[],
        wlan_configs=[],
        settings=settings or [],
        health=[],
        events=[],
    )


# ---------------------------------------------------------------------------
# aps property
# ---------------------------------------------------------------------------


def test_aps_filters_only_uap_type() -> None:
    devices = [
        DeviceInfo(mac="aa:bb:cc:dd:ee:01", type="uap", name="AP-Living"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:02", type="usw", name="Switch-Main"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:03", type="uap", name="AP-Office"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:04", type="ugw", name="Gateway"),
    ]
    snap = _make_snapshot(devices=devices)
    aps = snap.aps
    assert len(aps) == 2
    assert all(ap.type == "uap" for ap in aps)
    assert {ap.name for ap in aps} == {"AP-Living", "AP-Office"}


def test_aps_empty_when_no_aps() -> None:
    devices = [
        DeviceInfo(mac="aa:bb:cc:dd:ee:01", type="usw", name="Switch"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:02", type="ugw", name="Gateway"),
    ]
    snap = _make_snapshot(devices=devices)
    assert snap.aps == []


# ---------------------------------------------------------------------------
# gateway property
# ---------------------------------------------------------------------------


def test_gateway_returns_ugw() -> None:
    devices = [
        DeviceInfo(mac="aa:bb:cc:dd:ee:01", type="uap", name="AP"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:02", type="ugw", name="USG"),
    ]
    snap = _make_snapshot(devices=devices)
    gw = snap.gateway
    assert gw is not None
    assert gw.name == "USG"
    assert gw.type == "ugw"


def test_gateway_returns_udm() -> None:
    devices = [
        DeviceInfo(mac="aa:bb:cc:dd:ee:01", type="uap", name="AP"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:02", type="udm", name="UDM-Pro"),
    ]
    snap = _make_snapshot(devices=devices)
    gw = snap.gateway
    assert gw is not None
    assert gw.name == "UDM-Pro"
    assert gw.type == "udm"


def test_gateway_returns_none() -> None:
    devices = [
        DeviceInfo(mac="aa:bb:cc:dd:ee:01", type="uap", name="AP"),
        DeviceInfo(mac="aa:bb:cc:dd:ee:02", type="usw", name="Switch"),
    ]
    snap = _make_snapshot(devices=devices)
    assert snap.gateway is None


# ---------------------------------------------------------------------------
# clients_for_ap
# ---------------------------------------------------------------------------


def test_clients_for_ap() -> None:
    ap_mac = "aa:bb:cc:dd:ee:01"
    clients = [
        ClientInfo(mac="11:22:33:44:55:01", ap_mac=ap_mac, hostname="phone"),
        ClientInfo(mac="11:22:33:44:55:02", ap_mac="ff:ff:ff:ff:ff:ff", hostname="laptop"),
        ClientInfo(mac="11:22:33:44:55:03", ap_mac=ap_mac, hostname="tv"),
    ]
    snap = _make_snapshot(clients=clients)
    matched = snap.clients_for_ap(ap_mac)
    assert len(matched) == 2
    assert {c.hostname for c in matched} == {"phone", "tv"}


def test_clients_for_ap_empty() -> None:
    clients = [
        ClientInfo(mac="11:22:33:44:55:01", ap_mac="aa:aa:aa:aa:aa:aa", hostname="phone"),
    ]
    snap = _make_snapshot(clients=clients)
    assert snap.clients_for_ap("bb:bb:bb:bb:bb:bb") == []


# ---------------------------------------------------------------------------
# setting_by_key
# ---------------------------------------------------------------------------


def test_setting_by_key_found() -> None:
    settings = [
        SiteSetting(key="ips", ips_mode="ids"),
        SiteSetting(key="dpi", dpi_enabled=True),
    ]
    snap = _make_snapshot(settings=settings)
    result = snap.setting_by_key("dpi")
    assert result is not None
    assert result.key == "dpi"
    assert result.dpi_enabled is True


def test_setting_by_key_not_found() -> None:
    settings = [
        SiteSetting(key="ips", ips_mode="ids"),
    ]
    snap = _make_snapshot(settings=settings)
    assert snap.setting_by_key("nonexistent") is None


# ---------------------------------------------------------------------------
# get_setting_value
# ---------------------------------------------------------------------------


def test_get_setting_value_from_model_field() -> None:
    settings = [
        SiteSetting(key="ips", ips_mode="ids"),
    ]
    snap = _make_snapshot(settings=settings)
    assert snap.get_setting_value("ips", "ips_mode") == "ids"


def test_get_setting_value_from_model_extra() -> None:
    # SiteSetting uses extra="allow", so unknown fields go into model_extra
    settings = [
        SiteSetting(key="custom", **{"custom_field": "custom_value"}),
    ]
    snap = _make_snapshot(settings=settings)
    assert snap.get_setting_value("custom", "custom_field") == "custom_value"


def test_get_setting_value_default() -> None:
    settings = [
        SiteSetting(key="ips", ips_mode="ids"),
    ]
    snap = _make_snapshot(settings=settings)
    # Key not found at all
    assert snap.get_setting_value("missing_key", "ips_mode", "fallback") == "fallback"


def test_get_setting_value_attr_not_found() -> None:
    settings = [
        SiteSetting(key="ips", ips_mode="ids"),
    ]
    snap = _make_snapshot(settings=settings)
    # Key found but attribute does not exist on the model or in extras
    assert snap.get_setting_value("ips", "nonexistent_attr", "default_val") == "default_val"
