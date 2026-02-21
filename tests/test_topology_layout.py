"""Tests for topology/layout.py — spring-force layout engine."""

from __future__ import annotations

import math

from unifi_doctor.models.types import APLink, APPlacement, BarrierType, FloorLevel, Topology
from unifi_doctor.topology.layout import compute_layout


def _make_topology(n: int, links: list[APLink] | None = None) -> Topology:
    """Helper to create a topology with n APs."""
    placements = [
        APPlacement(mac=f"aa:bb:cc:dd:ee:{i:02x}", name=f"AP-{i}", floor=FloorLevel.GROUND) for i in range(n)
    ]
    return Topology(placements=placements, links=links or [])


def test_empty_topology():
    topo = _make_topology(0)
    result = compute_layout(topo)
    assert result.positions == []


def test_single_ap():
    topo = _make_topology(1)
    result = compute_layout(topo)
    assert len(result.positions) == 1
    assert result.positions[0].x == 0.5
    assert result.positions[0].y == 0.5
    assert result.positions[0].name == "AP-0"


def test_two_aps():
    topo = _make_topology(2)
    result = compute_layout(topo)
    assert len(result.positions) == 2
    # Should be on a horizontal line
    assert result.positions[0].y == result.positions[1].y == 0.5
    assert result.positions[0].x < result.positions[1].x


def test_three_aps_all_positions_in_bounds():
    topo = _make_topology(3)
    result = compute_layout(topo)
    assert len(result.positions) == 3
    for pos in result.positions:
        assert 0.0 <= pos.x <= 1.0
        assert 0.0 <= pos.y <= 1.0


def test_eight_aps_no_overlap():
    topo = _make_topology(8)
    result = compute_layout(topo)
    assert len(result.positions) == 8
    # No two nodes should be at the exact same position
    coords = [(p.x, p.y) for p in result.positions]
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            dist = math.sqrt((coords[i][0] - coords[j][0]) ** 2 + (coords[i][1] - coords[j][1]) ** 2)
            assert dist > 0.01, f"Nodes {i} and {j} overlap"


def test_deterministic_output():
    topo = _make_topology(5)
    r1 = compute_layout(topo, seed=42)
    r2 = compute_layout(topo, seed=42)
    for p1, p2 in zip(r1.positions, r2.positions):
        assert p1.x == p2.x
        assert p1.y == p2.y


def test_different_seed_different_output():
    topo = _make_topology(5)
    r1 = compute_layout(topo, seed=42)
    r2 = compute_layout(topo, seed=99)
    # At least some positions should differ
    any_diff = any(p1.x != p2.x or p1.y != p2.y for p1, p2 in zip(r1.positions, r2.positions))
    assert any_diff


def test_relative_distance_preservation():
    """Closer APs in distance_ft should be closer in layout coordinates."""
    links = [
        APLink(ap1_mac="aa:bb:cc:dd:ee:00", ap2_mac="aa:bb:cc:dd:ee:01", distance_ft=10, barrier=BarrierType.OPEN_AIR),
        APLink(ap1_mac="aa:bb:cc:dd:ee:00", ap2_mac="aa:bb:cc:dd:ee:02", distance_ft=80, barrier=BarrierType.WALL),
        APLink(ap1_mac="aa:bb:cc:dd:ee:01", ap2_mac="aa:bb:cc:dd:ee:02", distance_ft=75, barrier=BarrierType.WALL),
    ]
    topo = _make_topology(3, links=links)
    result = compute_layout(topo, iterations=1000)

    pos = {p.mac: (p.x, p.y) for p in result.positions}

    def dist(mac_a: str, mac_b: str) -> float:
        ax, ay = pos[mac_a]
        bx, by = pos[mac_b]
        return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)

    d_close = dist("aa:bb:cc:dd:ee:00", "aa:bb:cc:dd:ee:01")
    d_far = dist("aa:bb:cc:dd:ee:00", "aa:bb:cc:dd:ee:02")

    # The close pair (10ft) should be closer than the far pair (80ft)
    assert d_close < d_far, f"Close pair ({d_close:.3f}) should be < far pair ({d_far:.3f})"


def test_no_links_still_works():
    """APs with no distance links should still get valid positions via repulsion."""
    topo = _make_topology(4)
    result = compute_layout(topo)
    assert len(result.positions) == 4
    for pos in result.positions:
        assert 0.0 <= pos.x <= 1.0
        assert 0.0 <= pos.y <= 1.0
