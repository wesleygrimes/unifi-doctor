"""Tests for Pydantic model properties and behaviors."""

from __future__ import annotations

from datetime import datetime

from unifi_doctor.models.types import (
    ClientInfo,
    DeviceInfo,
    DiagnosticReport,
    Event,
    Finding,
    Severity,
    WLANConfig,
)

# ---------------------------------------------------------------------------
# ClientInfo property tests
# ---------------------------------------------------------------------------


def test_client_is_5g_true_when_channel_above_14():
    client = ClientInfo(channel=36)
    assert client.is_5g is True


def test_client_is_2g_true_when_channel_between_1_and_14():
    client = ClientInfo(channel=6)
    assert client.is_2g is True


def test_client_is_2g_false_when_channel_is_zero():
    client = ClientInfo(channel=0)
    assert client.is_2g is False


def test_client_display_name_prefers_name():
    client = ClientInfo(mac="aa:bb:cc:dd:ee:ff", hostname="myhost", name="My Device")
    assert client.display_name == "My Device"


def test_client_display_name_falls_back_to_hostname():
    client = ClientInfo(mac="aa:bb:cc:dd:ee:ff", hostname="myhost", name="")
    assert client.display_name == "myhost"


def test_client_display_name_falls_back_to_mac():
    client = ClientInfo(mac="aa:bb:cc:dd:ee:ff", hostname="", name="")
    assert client.display_name == "aa:bb:cc:dd:ee:ff"


def test_client_is_guest_accessible_as_regular_field():
    client = ClientInfo(is_guest=True)
    assert client.is_guest is True

    client_default = ClientInfo()
    assert client_default.is_guest is False


# ---------------------------------------------------------------------------
# DeviceInfo property tests
# ---------------------------------------------------------------------------


def test_device_is_ap_true_for_uap():
    device = DeviceInfo(type="uap")
    assert device.is_ap is True


def test_device_is_ap_false_for_non_ap_types():
    assert DeviceInfo(type="usw").is_ap is False
    assert DeviceInfo(type="ugw").is_ap is False


def test_device_is_gateway_true_for_ugw_and_udm():
    assert DeviceInfo(type="ugw").is_gateway is True
    assert DeviceInfo(type="udm").is_gateway is True


def test_device_display_name_returns_name_if_set():
    device = DeviceInfo(mac="aa:bb:cc:dd:ee:ff", name="Living Room AP")
    assert device.display_name == "Living Room AP"


def test_device_display_name_falls_back_to_mac():
    device = DeviceInfo(mac="aa:bb:cc:dd:ee:ff", name="")
    assert device.display_name == "aa:bb:cc:dd:ee:ff"


# ---------------------------------------------------------------------------
# DiagnosticReport severity filter tests
# ---------------------------------------------------------------------------


def _make_finding(severity: Severity, title: str = "Test") -> Finding:
    return Finding(
        severity=severity,
        module="test",
        title=title,
        detail="detail",
        recommendation="recommendation",
    )


def test_diagnostic_report_critical_filters():
    report = DiagnosticReport(
        findings=[
            _make_finding(Severity.CRITICAL, "crit1"),
            _make_finding(Severity.WARNING, "warn1"),
            _make_finding(Severity.CRITICAL, "crit2"),
        ]
    )
    assert len(report.critical) == 2
    assert all(f.severity == Severity.CRITICAL for f in report.critical)


def test_diagnostic_report_warnings_filters():
    report = DiagnosticReport(
        findings=[
            _make_finding(Severity.WARNING, "warn1"),
            _make_finding(Severity.CRITICAL, "crit1"),
            _make_finding(Severity.WARNING, "warn2"),
        ]
    )
    assert len(report.warnings) == 2
    assert all(f.severity == Severity.WARNING for f in report.warnings)


def test_diagnostic_report_info_filters():
    report = DiagnosticReport(
        findings=[
            _make_finding(Severity.INFO, "info1"),
            _make_finding(Severity.GOOD, "good1"),
            _make_finding(Severity.INFO, "info2"),
        ]
    )
    assert len(report.info) == 2
    assert all(f.severity == Severity.INFO for f in report.info)


def test_diagnostic_report_good_filters():
    report = DiagnosticReport(
        findings=[
            _make_finding(Severity.GOOD, "good1"),
            _make_finding(Severity.INFO, "info1"),
            _make_finding(Severity.GOOD, "good2"),
        ]
    )
    assert len(report.good) == 2
    assert all(f.severity == Severity.GOOD for f in report.good)


# ---------------------------------------------------------------------------
# Event timestamp tests
# ---------------------------------------------------------------------------


def test_event_timestamp_returns_datetime_from_epoch():
    event = Event(time=1700000000)
    ts = event.timestamp
    assert isinstance(ts, datetime)
    assert ts == datetime.fromtimestamp(1700000000)


def test_event_timestamp_returns_datetime_min_when_zero():
    event = Event(time=0)
    assert event.timestamp == datetime.min


# ---------------------------------------------------------------------------
# WLANConfig alias tests
# ---------------------------------------------------------------------------


def test_wlanconfig_with_alias_id():
    wlan = WLANConfig(_id="abc123", name="TestNet")
    assert wlan.id == "abc123"


def test_wlanconfig_with_field_name_id():
    wlan = WLANConfig(id="def456", name="TestNet")
    assert wlan.id == "def456"


# ---------------------------------------------------------------------------
# Extra fields test
# ---------------------------------------------------------------------------


def test_device_info_extra_fields_allowed():
    device = DeviceInfo(
        mac="aa:bb:cc:dd:ee:ff",
        type="uap",
        some_unknown_field="hello",
        another_field=42,
    )
    assert device.mac == "aa:bb:cc:dd:ee:ff"
    assert device.model_extra["some_unknown_field"] == "hello"
    assert device.model_extra["another_field"] == 42
