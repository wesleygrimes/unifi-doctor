"""Tests for config and topology save/load round-trips."""

from __future__ import annotations

from unifi_doctor.api.client import (
    load_config,
    load_topology,
    save_config,
    save_topology,
)
from unifi_doctor.models.types import (
    APLink,
    APPlacement,
    BackhaulType,
    BarrierType,
    Config,
    ControllerConfig,
    FloorLevel,
    Topology,
)

# ---------------------------------------------------------------------------
# Topology round-trip tests
# ---------------------------------------------------------------------------


def test_save_topology_produces_safe_yaml(tmp_path, monkeypatch):
    """Saved topology YAML must not contain Python-specific tags."""
    topo = Topology(
        placements=[
            APPlacement(
                mac="aa:bb:cc:dd:ee:01",
                name="Living Room",
                floor=FloorLevel.UPPER,
                location_description="hallway ceiling",
                backhaul=BackhaulType.WIRED,
            ),
        ],
        links=[
            APLink(
                ap1_mac="aa:bb:cc:dd:ee:01",
                ap2_mac="aa:bb:cc:dd:ee:02",
                distance_ft=25.0,
                barrier=BarrierType.WALL,
            ),
        ],
    )

    topo_file = tmp_path / "topology.yaml"
    monkeypatch.setattr("unifi_doctor.api.client.TOPOLOGY_FILE", topo_file)
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_DIR", tmp_path)

    save_topology(topo)

    raw_text = topo_file.read_text()
    assert "!!python" not in raw_text, f"YAML contains Python-specific tags:\n{raw_text}"


def test_topology_save_load_round_trip(tmp_path, monkeypatch):
    """Topology should survive a save → load cycle with all values intact."""
    topo = Topology(
        placements=[
            APPlacement(
                mac="aa:bb:cc:dd:ee:01",
                name="Office AP",
                floor=FloorLevel.GROUND,
                location_description="desk mount",
                backhaul=BackhaulType.WIRED,
            ),
            APPlacement(
                mac="aa:bb:cc:dd:ee:02",
                name="Garage AP",
                floor=FloorLevel.DETACHED,
                location_description="garage wall",
                backhaul=BackhaulType.WIRELESS_MESH,
            ),
        ],
        links=[
            APLink(
                ap1_mac="aa:bb:cc:dd:ee:01",
                ap2_mac="aa:bb:cc:dd:ee:02",
                distance_ft=50.0,
                barrier=BarrierType.OUTDOOR,
            ),
        ],
    )

    topo_file = tmp_path / "topology.yaml"
    monkeypatch.setattr("unifi_doctor.api.client.TOPOLOGY_FILE", topo_file)
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_DIR", tmp_path)

    save_topology(topo)
    loaded = load_topology()

    assert len(loaded.placements) == 2
    assert loaded.placements[0].mac == "aa:bb:cc:dd:ee:01"
    assert loaded.placements[0].floor == FloorLevel.GROUND
    assert loaded.placements[0].backhaul == BackhaulType.WIRED
    assert loaded.placements[1].floor == FloorLevel.DETACHED
    assert loaded.placements[1].backhaul == BackhaulType.WIRELESS_MESH

    assert len(loaded.links) == 1
    assert loaded.links[0].barrier == BarrierType.OUTDOOR
    assert loaded.links[0].distance_ft == 50.0


def test_topology_round_trip_all_enum_values(tmp_path, monkeypatch):
    """Every BarrierType and FloorLevel value must round-trip correctly."""
    topo_file = tmp_path / "topology.yaml"
    monkeypatch.setattr("unifi_doctor.api.client.TOPOLOGY_FILE", topo_file)
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_DIR", tmp_path)

    placements = [
        APPlacement(mac=f"aa:bb:cc:dd:ee:{i:02d}", name=f"AP-{fl.value}", floor=fl)
        for i, fl in enumerate(FloorLevel)
    ]
    links = [
        APLink(ap1_mac="aa:bb:cc:dd:ee:00", ap2_mac=f"aa:bb:cc:dd:ee:{i + 1:02d}", barrier=bt)
        for i, bt in enumerate(BarrierType)
    ]

    topo = Topology(placements=placements, links=links)
    save_topology(topo)
    loaded = load_topology()

    for orig, loaded_p in zip(topo.placements, loaded.placements):
        assert loaded_p.floor == orig.floor

    for orig, loaded_l in zip(topo.links, loaded.links):
        assert loaded_l.barrier == orig.barrier


def test_load_topology_returns_default_when_file_missing(tmp_path, monkeypatch):
    """load_topology() returns empty Topology when no file exists."""
    monkeypatch.setattr("unifi_doctor.api.client.TOPOLOGY_FILE", tmp_path / "nonexistent.yaml")

    topo = load_topology()
    assert topo.placements == []
    assert topo.links == []


def test_load_topology_handles_empty_file(tmp_path, monkeypatch):
    """load_topology() handles an empty YAML file gracefully."""
    topo_file = tmp_path / "topology.yaml"
    topo_file.write_text("")
    monkeypatch.setattr("unifi_doctor.api.client.TOPOLOGY_FILE", topo_file)

    topo = load_topology()
    assert topo.placements == []
    assert topo.links == []


# ---------------------------------------------------------------------------
# Config round-trip tests
# ---------------------------------------------------------------------------


def test_config_save_load_round_trip(tmp_path, monkeypatch):
    """Config should survive a save → load cycle."""
    cfg = Config(
        controller=ControllerConfig(
            host="https://10.0.0.1",
            username="testuser",
            password="secret123",
            site="mysite",
        )
    )

    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_FILE", config_file)
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_DIR", tmp_path)
    # Clear env vars so they don't override
    monkeypatch.delenv("UNIFI_HOST", raising=False)
    monkeypatch.delenv("UNIFI_USER", raising=False)
    monkeypatch.delenv("UNIFI_PASS", raising=False)

    save_config(cfg)
    loaded = load_config()

    assert loaded.controller.host == "https://10.0.0.1"
    assert loaded.controller.username == "testuser"
    assert loaded.controller.password == "secret123"
    assert loaded.controller.site == "mysite"


def test_load_config_returns_default_when_file_missing(tmp_path, monkeypatch):
    """load_config() returns default Config when no file exists."""
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_FILE", tmp_path / "nonexistent.yaml")
    monkeypatch.delenv("UNIFI_HOST", raising=False)
    monkeypatch.delenv("UNIFI_USER", raising=False)
    monkeypatch.delenv("UNIFI_PASS", raising=False)

    cfg = load_config()
    assert cfg.controller.host == "https://192.168.1.1"
    assert cfg.controller.username == "admin"


def test_load_config_env_var_overrides(tmp_path, monkeypatch):
    """Environment variables should override config file values."""
    config_file = tmp_path / "config.yaml"
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_FILE", config_file)
    monkeypatch.setattr("unifi_doctor.api.client.CONFIG_DIR", tmp_path)

    cfg = Config(controller=ControllerConfig(host="https://10.0.0.1", username="fileuser", password="filepass"))
    save_config(cfg)

    monkeypatch.setenv("UNIFI_HOST", "https://env-host.local")
    monkeypatch.setenv("UNIFI_USER", "envuser")
    monkeypatch.setenv("UNIFI_PASS", "envpass")

    loaded = load_config()
    assert loaded.controller.host == "https://env-host.local"
    assert loaded.controller.username == "envuser"
    assert loaded.controller.password == "envpass"
