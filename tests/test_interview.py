"""Tests for topology interview helpers."""

from __future__ import annotations

from unifi_doctor.models.types import BackhaulType, DeviceInfo, FloorLevel
from unifi_doctor.topology.interview import _default_floor, _detect_backhaul, _parse_floor_location

# ---------------------------------------------------------------------------
# Backhaul auto-detection
# ---------------------------------------------------------------------------


def _make_ap(name: str = "Test-AP", uplink_type: str = "", mesh_sta_vap_enabled: bool = False) -> DeviceInfo:
    return DeviceInfo(
        mac="aa:bb:cc:dd:ee:01",
        name=name,
        type="uap",
        model="U6-LR",
        uplink_type=uplink_type,
        mesh_sta_vap_enabled=mesh_sta_vap_enabled,
    )


def test_detect_backhaul_wired():
    ap = _make_ap(uplink_type="wire")
    assert _detect_backhaul(ap, []) == BackhaulType.WIRED


def test_detect_backhaul_wireless_uplink():
    ap = _make_ap(uplink_type="wireless")
    assert _detect_backhaul(ap, []) == BackhaulType.WIRELESS_MESH


def test_detect_backhaul_mesh_enabled():
    ap = _make_ap(mesh_sta_vap_enabled=True)
    assert _detect_backhaul(ap, []) == BackhaulType.WIRELESS_MESH


def test_detect_backhaul_default_is_wired():
    ap = _make_ap()
    assert _detect_backhaul(ap, []) == BackhaulType.WIRED


# ---------------------------------------------------------------------------
# Smart floor defaults
# ---------------------------------------------------------------------------


def test_default_floor_normal_ap():
    ap = _make_ap(name="Living Room")
    assert _default_floor(ap) == "1"  # GROUND


def test_default_floor_garage():
    ap = _make_ap(name="Garage AP")
    assert _default_floor(ap) == "4"  # DETACHED


def test_default_floor_outdoor():
    ap = _make_ap(name="Outdoor-Patio")
    assert _default_floor(ap) == "4"


def test_default_floor_shed():
    ap = _make_ap(name="Shed")
    assert _default_floor(ap) == "4"


def test_default_floor_porch():
    ap = _make_ap(name="Front Porch AP")
    assert _default_floor(ap) == "4"


def test_default_floor_deck():
    ap = _make_ap(name="Back Deck")
    assert _default_floor(ap) == "4"


def test_default_floor_yard():
    ap = _make_ap(name="Yard")
    assert _default_floor(ap) == "4"


# ---------------------------------------------------------------------------
# Combined floor + location parsing
# ---------------------------------------------------------------------------


def test_parse_floor_location_with_name_and_location():
    floor, loc = _parse_floor_location("ground, hallway ceiling")
    assert floor == FloorLevel.GROUND
    assert loc == "hallway ceiling"


def test_parse_floor_location_numeric_with_location():
    floor, loc = _parse_floor_location("2, living room")
    assert floor == FloorLevel.UPPER
    assert loc == "living room"


def test_parse_floor_location_name_only():
    floor, loc = _parse_floor_location("basement")
    assert floor == FloorLevel.BASEMENT
    assert loc == ""


def test_parse_floor_location_numeric_only():
    floor, loc = _parse_floor_location("4")
    assert floor == FloorLevel.DETACHED
    assert loc == ""


def test_parse_floor_location_detached_with_location():
    floor, loc = _parse_floor_location("detached, separate building")
    assert floor == FloorLevel.DETACHED
    assert loc == "separate building"


def test_parse_floor_location_unknown_defaults_to_ground():
    floor, loc = _parse_floor_location("attic, top floor")
    assert floor == FloorLevel.GROUND
    assert loc == "top floor"
