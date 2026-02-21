"""Pydantic models for UniFi API responses, config, topology, and diagnostics."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(enum.StrEnum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"
    GOOD = "good"


class Band(enum.StrEnum):
    BAND_2G = "2g"
    BAND_5G = "5g"
    BAND_6G = "6g"


class BackhaulType(enum.StrEnum):
    WIRED = "wired"
    WIRELESS_MESH = "wireless_mesh"


class BarrierType(enum.StrEnum):
    WALL = "wall"
    FLOOR_CEILING = "floor_ceiling"
    OUTDOOR = "outdoor"
    OPEN_AIR = "open_air"


class FloorLevel(enum.StrEnum):
    GROUND = "ground"
    UPPER = "upper"
    BASEMENT = "basement"
    DETACHED = "detached"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class ControllerConfig(BaseModel):
    host: str = "https://192.168.1.1"
    username: str = "admin"
    password: str = ""
    site: str = "default"
    verify_ssl: bool = False


class Config(BaseModel):
    controller: ControllerConfig = Field(default_factory=ControllerConfig)


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------


class APPlacement(BaseModel):
    mac: str
    name: str
    floor: FloorLevel = FloorLevel.GROUND
    location_description: str = ""
    backhaul: BackhaulType = BackhaulType.WIRED


class APLink(BaseModel):
    ap1_mac: str
    ap2_mac: str
    distance_ft: float = 0.0
    barrier: BarrierType = BarrierType.WALL


class Topology(BaseModel):
    placements: list[APPlacement] = Field(default_factory=list)
    links: list[APLink] = Field(default_factory=list)


class APCoordinate(BaseModel):
    mac: str
    name: str
    floor: FloorLevel = FloorLevel.GROUND
    x: float = 0.0
    y: float = 0.0
    client_count: int | None = None


class TopologyMapResult(BaseModel):
    nodes: list[APCoordinate] = Field(default_factory=list)
    links: list[APLink] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API Response Models (loose – extra fields allowed)
# ---------------------------------------------------------------------------


class RadioTableEntry(BaseModel, extra="allow"):
    radio: str = ""
    name: str = ""
    channel: int | str = 0
    ht: int = 20
    tx_power: int = 0
    tx_power_mode: str = "auto"
    min_rssi_enabled: bool = False
    min_rssi: int = 0
    nss: int = 1
    cu_total: int = 0  # channel utilization
    cu_self_rx: int = 0
    cu_self_tx: int = 0
    satisfaction: int = 100
    noise_floor: int = -100  # Added for noise floor checks

    @field_validator("satisfaction", mode="before")
    @classmethod
    def _coerce_satisfaction(cls, v: Any) -> int:
        return v if v is not None else 100


class RadioTableStatsEntry(BaseModel, extra="allow"):
    name: str = ""
    channel: int | str = 0
    cu_total: int = 0
    cu_self_rx: int = 0
    cu_self_tx: int = 0
    noise_floor: int = -100  # Added for noise floor checks
    satisfaction: int = 100
    num_sta: int = 0

    @field_validator("satisfaction", mode="before")
    @classmethod
    def _coerce_satisfaction(cls, v: Any) -> int:
        return v if v is not None else 100


class PortTableEntry(BaseModel, extra="allow"):
    port_idx: int = 0
    name: str = ""
    speed: int = 0
    full_duplex: bool = True
    rx_errors: int = 0
    tx_errors: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    up: bool = False


class UplinkInfo(BaseModel, extra="allow"):
    type: str = ""
    speed: int = 0
    full_duplex: bool = True
    max_speed: int = 0


class DeviceInfo(BaseModel, extra="allow"):
    """Represents a UniFi device (AP, switch, gateway)."""

    mac: str = ""
    name: str = ""
    model: str = ""
    type: str = ""  # uap, usw, ugw, udm
    state: int = 1
    adopted: bool = True
    version: str = ""
    ip: str = ""
    uptime: int = 0
    satisfaction: int = 100
    radio_table: list[RadioTableEntry] = Field(default_factory=list)
    radio_table_stats: list[RadioTableStatsEntry] = Field(default_factory=list)
    port_table: list[PortTableEntry] = Field(default_factory=list)
    uplink: UplinkInfo | None = None
    mesh_sta_vap_enabled: bool = False
    uplink_type: str = ""  # "wire" or "wireless"

    @field_validator("satisfaction", mode="before")
    @classmethod
    def _coerce_satisfaction(cls, v: Any) -> int:
        return v if v is not None else 100

    @property
    def is_ap(self) -> bool:
        return self.type in ("uap",)

    @property
    def is_gateway(self) -> bool:
        return self.type in ("ugw", "udm")

    @property
    def display_name(self) -> str:
        return self.name or self.mac


class ClientInfo(BaseModel, extra="allow"):
    """Represents a connected client."""

    mac: str = ""
    hostname: str = ""
    name: str = ""
    oui: str = ""
    ip: str = ""
    ap_mac: str = ""
    essid: str = ""
    bssid: str = ""
    channel: int = 0
    radio: str = ""
    radio_proto: str = ""  # eg "ac", "ax", "n", "b", "g"
    rssi: int = 0
    signal: int = 0
    noise: int = 0
    tx_rate: int = 0
    rx_rate: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    satisfaction: int = 100
    is_wired: bool = False
    is_guest: bool = False
    roam_count: int = 0
    uptime: int = 0
    last_seen: int = 0

    @field_validator("satisfaction", mode="before")
    @classmethod
    def _coerce_satisfaction(cls, v: Any) -> int:
        return v if v is not None else 100

    @property
    def display_name(self) -> str:
        return self.name or self.hostname or self.mac

    @property
    def is_5g(self) -> bool:
        return self.channel > 14

    @property
    def is_2g(self) -> bool:
        return 0 < self.channel <= 14


class RogueAP(BaseModel, extra="allow"):
    mac: str = ""
    essid: str = ""
    channel: int = 0
    rssi: int = 0
    age: int = 0
    radio: str = ""
    report_time: int = 0
    ap_mac: str = ""  # which of our APs detected this


class WLANConfig(BaseModel, extra="allow"):
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field("", alias="_id")
    name: str = ""
    enabled: bool = True
    wpa_mode: str = ""
    dtim_mode: str = "default"
    dtim_na: int = 1
    dtim_ng: int = 1
    fast_roaming_enabled: bool = False
    rrm_enabled: bool = False  # 802.11k
    bss_transition: bool = False  # 802.11v
    band_steering_mode: str = "off"
    min_rssi_enabled: bool = False
    min_rssi: int = 0
    pmf_mode: str = "disabled"
    multicast_enhance: bool = False
    igmp_snooping: bool = False
    wlan_band: str = "both"


class SiteSetting(BaseModel, extra="allow"):
    key: str = ""
    # IDS/IPS
    ips_mode: str = ""  # "ids", "ips", "disabled"
    # DPI
    dpi_enabled: bool = False
    # Smart Queues
    sqm_enabled: bool = False
    sqm_download_rate: int = 0
    sqm_upload_rate: int = 0
    # DNS
    dns1: str = ""
    dns2: str = ""
    # UPnP
    upnp_enabled: bool = False
    # Connectivity Monitor
    connectivity_type: str = ""
    connectivity_host: str = ""
    # Auto optimize
    auto_optimize_enabled: bool = False


class HealthSubsystem(BaseModel, extra="allow"):
    subsystem: str = ""
    status: str = ""
    num_ap: int = 0
    num_sta: int = 0
    num_adopted: int = 0
    num_pending: int = 0
    wan_ip: str = ""
    tx_bytes_r: int = 0
    rx_bytes_r: int = 0
    latency: int = 0
    uptime: int = 0
    drops: int = 0
    xput_down: float = 0.0
    xput_up: float = 0.0
    speedtest_lastrun: int = 0


class Event(BaseModel, extra="allow"):
    key: str = ""
    msg: str = ""
    time: int = 0
    datetime_val: str = Field("", alias="datetime")
    ap: str = ""
    ap_name: str = ""
    user: str = ""
    ssid: str = ""
    channel: int = 0
    guest: str = ""
    subsystem: str = ""

    @property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.time) if self.time else datetime.min


# ---------------------------------------------------------------------------
# Diagnostic Output
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    severity: Severity
    module: str
    title: str
    detail: str
    recommendation: str
    ui_path: str = ""  # e.g. "Settings > Internet Security > Threat Management"
    api_change: dict[str, Any] | None = None  # for apply-plan


class ChannelPlan(BaseModel):
    ap_mac: str
    ap_name: str
    band: Band
    current_channel: int | str = 0
    recommended_channel: int = 0
    current_width: int = 20
    recommended_width: int = 20
    current_power: str = ""
    recommended_power: str = ""
    reason: str = ""


class DiagnosticReport(BaseModel):
    generated_at: datetime = Field(default_factory=datetime.now)
    modules_run: list[str] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    channel_plan: list[ChannelPlan] = Field(default_factory=list)

    @property
    def critical(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.CRITICAL]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.WARNING]

    @property
    def info(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.INFO]

    @property
    def good(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == Severity.GOOD]
