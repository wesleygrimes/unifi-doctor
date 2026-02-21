"""Tests for output/topology_output.py — JSON structure."""

from __future__ import annotations

from unifi_doctor.models.types import APLink, APPlacement, BarrierType, FloorLevel, Topology
from unifi_doctor.output.topology_output import topology_to_json


def _make_topology() -> Topology:
    return Topology(
        placements=[
            APPlacement(mac="aa:bb:cc:dd:ee:00", name="Office", floor=FloorLevel.GROUND),
            APPlacement(mac="aa:bb:cc:dd:ee:01", name="Kitchen", floor=FloorLevel.UPPER),
        ],
        links=[
            APLink(
                ap1_mac="aa:bb:cc:dd:ee:00",
                ap2_mac="aa:bb:cc:dd:ee:01",
                distance_ft=25,
                barrier=BarrierType.FLOOR_CEILING,
            ),
        ],
    )


def test_json_structure():
    topo = _make_topology()
    data = topology_to_json(topo)

    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) == 2
    assert len(data["links"]) == 1

    node = data["nodes"][0]
    assert "mac" in node
    assert "name" in node
    assert "floor" in node
    assert "x" in node
    assert "y" in node
    assert isinstance(node["x"], float)
    assert isinstance(node["y"], float)
    assert 0.0 <= node["x"] <= 1.0
    assert 0.0 <= node["y"] <= 1.0


def test_json_with_client_counts():
    topo = _make_topology()
    counts = {"aa:bb:cc:dd:ee:00": 8, "aa:bb:cc:dd:ee:01": 3}
    data = topology_to_json(topo, client_counts=counts)

    node_lookup = {n["mac"]: n for n in data["nodes"]}
    assert node_lookup["aa:bb:cc:dd:ee:00"]["client_count"] == 8
    assert node_lookup["aa:bb:cc:dd:ee:01"]["client_count"] == 3


def test_json_without_client_counts():
    topo = _make_topology()
    data = topology_to_json(topo)

    for node in data["nodes"]:
        assert node["client_count"] is None


def test_json_link_structure():
    topo = _make_topology()
    data = topology_to_json(topo)
    link = data["links"][0]
    assert link["ap1_mac"] == "aa:bb:cc:dd:ee:00"
    assert link["ap2_mac"] == "aa:bb:cc:dd:ee:01"
    assert link["distance_ft"] == 25.0
    assert link["barrier"] == "floor_ceiling"


def test_json_empty_topology():
    topo = Topology()
    data = topology_to_json(topo)
    assert data["nodes"] == []
    assert data["links"] == []
