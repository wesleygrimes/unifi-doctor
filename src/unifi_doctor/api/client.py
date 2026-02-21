"""UniFi API client — handles auth, session management, and data fetching."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
import yaml
from rich.console import Console

from unifi_doctor.api import endpoints as ep
from unifi_doctor.models.types import (
    ClientInfo,
    Config,
    ControllerConfig,
    DeviceInfo,
    Event,
    HealthSubsystem,
    RogueAP,
    SiteSetting,
    Topology,
    WLANConfig,
)

console = Console(stderr=True)

CONFIG_DIR = Path.home() / ".unifi-doctor"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
TOPOLOGY_FILE = CONFIG_DIR / "topology.yaml"


def load_config() -> Config:
    """Load config from file, with env-var overrides."""
    cfg = Config()
    if CONFIG_FILE.exists():
        raw = yaml.safe_load(CONFIG_FILE.read_text()) or {}
        ctrl = raw.get("controller", {})
        cfg = Config(controller=ControllerConfig(**ctrl))

    # Env-var overrides
    if host := os.environ.get("UNIFI_HOST"):
        cfg.controller.host = host
    if user := os.environ.get("UNIFI_USER"):
        cfg.controller.username = user
    if pw := os.environ.get("UNIFI_PASS"):
        cfg.controller.password = pw
    return cfg


def save_config(cfg: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    data = {"controller": cfg.controller.model_dump()}
    CONFIG_FILE.write_text(yaml.dump(data, default_flow_style=False))
    CONFIG_FILE.chmod(0o600)


def load_topology() -> Topology:
    if TOPOLOGY_FILE.exists():
        raw = yaml.safe_load(TOPOLOGY_FILE.read_text()) or {}
        return Topology(**raw)
    return Topology()


def save_topology(topo: Topology) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    TOPOLOGY_FILE.write_text(yaml.dump(topo.model_dump(mode="json"), default_flow_style=False))


class UniFiClient:
    """Async client for the UniFi controller local API."""

    def __init__(self, config: Config, verify_ssl: bool = False, verbose: bool = False):
        self.config = config
        self.verify_ssl = verify_ssl
        self.verbose = verbose
        self._client: httpx.AsyncClient | None = None
        self._authenticated = False

    async def __aenter__(self) -> UniFiClient:
        self._client = httpx.AsyncClient(
            base_url=self.config.controller.host.rstrip("/"),
            verify=self.verify_ssl,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )
        await self._authenticate()
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._client:
            await self._client.aclose()

    async def _authenticate(self) -> None:
        ctrl = self.config.controller
        payload = {"username": ctrl.username, "password": ctrl.password}
        try:
            resp = await self._client.post(ep.AUTH_LOGIN, json=payload)  # type: ignore[union-attr]
            resp.raise_for_status()
            self._authenticated = True
            if self.verbose:
                console.print(f"[green]Authenticated to {ctrl.host}[/green]")
        except httpx.HTTPStatusError as e:
            console.print(f"[red]Authentication failed: {e.response.status_code}[/red]")
            raise SystemExit(1)
        except httpx.ConnectError as e:
            console.print(f"[red]Cannot connect to {ctrl.host}: {e}[/red]")
            raise SystemExit(1)

    async def _get(self, path: str) -> list[dict[str, Any]]:
        """GET an endpoint, return the data array or empty list on failure."""
        try:
            resp = await self._client.get(path)  # type: ignore[union-attr]
            if self.verbose:
                console.print(f"[dim]GET {path} → {resp.status_code}[/dim]")
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            return body.get("data", [])
        except (httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
            if self.verbose:
                console.print(f"[yellow]Endpoint {path} failed: {e}[/yellow]")
            return []

    async def _post(self, path: str, payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        try:
            resp = await self._client.post(path, json=payload or {})  # type: ignore[union-attr]
            if resp.status_code == 404:
                return []
            resp.raise_for_status()
            body = resp.json()
            return body.get("data", [])
        except Exception as e:
            if self.verbose:
                console.print(f"[yellow]POST {path} failed: {e}[/yellow]")
            return []

    @property
    def site(self) -> str:
        return self.config.controller.site

    # -----------------------------------------------------------------------
    # High-level data fetchers
    # -----------------------------------------------------------------------

    async def get_devices(self) -> list[DeviceInfo]:
        data = await self._get(ep.stat_device(self.site))
        return [DeviceInfo(**d) for d in data]

    async def get_clients(self) -> list[ClientInfo]:
        data = await self._get(ep.stat_sta(self.site))
        return [ClientInfo(**d) for d in data]

    async def get_rogue_aps(self) -> list[RogueAP]:
        data = await self._get(ep.stat_rogueap(self.site))
        return [RogueAP(**d) for d in data]

    async def get_wlan_configs(self) -> list[WLANConfig]:
        data = await self._get(ep.rest_wlanconf(self.site))
        return [WLANConfig(**d) for d in data]

    async def get_site_settings(self) -> list[SiteSetting]:
        data = await self._get(ep.rest_setting(self.site))
        return [SiteSetting(**d) for d in data]

    async def get_health(self) -> list[HealthSubsystem]:
        data = await self._get(ep.stat_health(self.site))
        return [HealthSubsystem(**d) for d in data]

    async def get_events(self, limit: int = 500) -> list[Event]:
        # Use POST with params to get more events
        data = await self._get(ep.stat_event(self.site) + f"?_limit={limit}&_sort=-time")
        return [Event(**d) for d in data]

    async def get_routing(self) -> list[dict[str, Any]]:
        return await self._get(ep.stat_routing(self.site))

    async def get_spectral(self) -> list[dict[str, Any]]:
        return await self._get(ep.stat_spectral(self.site))

    async def get_all_raw(self) -> dict[str, list[dict[str, Any]]]:
        """Fetch all endpoints as raw dicts for JSON export."""
        results: dict[str, list[dict[str, Any]]] = {}
        fetchers = {
            "devices": ep.stat_device(self.site),
            "clients": ep.stat_sta(self.site),
            "rogue_aps": ep.stat_rogueap(self.site),
            "wlan_configs": ep.rest_wlanconf(self.site),
            "settings": ep.rest_setting(self.site),
            "health": ep.stat_health(self.site),
            "events": ep.stat_event(self.site),
            "routing": ep.stat_routing(self.site),
        }

        async def _fetch(key: str, path: str) -> None:
            results[key] = await self._get(path)

        await asyncio.gather(*[_fetch(k, v) for k, v in fetchers.items()])
        return results

    async def fetch_all(self) -> NetworkSnapshot:
        """Fetch all data concurrently and return a snapshot."""
        (
            devices,
            clients,
            rogue_aps,
            wlan_configs,
            settings,
            health,
            events,
        ) = await asyncio.gather(
            self.get_devices(),
            self.get_clients(),
            self.get_rogue_aps(),
            self.get_wlan_configs(),
            self.get_site_settings(),
            self.get_health(),
            self.get_events(),
        )
        return NetworkSnapshot(
            devices=devices,
            clients=clients,
            rogue_aps=rogue_aps,
            wlan_configs=wlan_configs,
            settings=settings,
            health=health,
            events=events,
        )

    async def send_device_command(self, mac: str, cmd: str, params: dict[str, Any] | None = None) -> bool:
        """Send a command to a device via the devmgr endpoint."""
        payload: dict[str, Any] = {"cmd": cmd, "mac": mac}
        if params:
            payload.update(params)
        data = await self._post(ep.device_mgmt(self.site, mac), payload)
        return len(data) > 0


class NetworkSnapshot:
    """In-memory snapshot of all network data for analysis."""

    def __init__(
        self,
        devices: list[DeviceInfo],
        clients: list[ClientInfo],
        rogue_aps: list[RogueAP],
        wlan_configs: list[WLANConfig],
        settings: list[SiteSetting],
        health: list[HealthSubsystem],
        events: list[Event],
    ):
        self.devices = devices
        self.clients = clients
        self.rogue_aps = rogue_aps
        self.wlan_configs = wlan_configs
        self.settings = settings
        self.health = health
        self.events = events

    @property
    def aps(self) -> list[DeviceInfo]:
        return [d for d in self.devices if d.is_ap]

    @property
    def gateway(self) -> DeviceInfo | None:
        gws = [d for d in self.devices if d.is_gateway]
        return gws[0] if gws else None

    def clients_for_ap(self, ap_mac: str) -> list[ClientInfo]:
        return [c for c in self.clients if c.ap_mac == ap_mac]

    def setting_by_key(self, key: str) -> SiteSetting | None:
        for s in self.settings:
            if s.key == key:
                return s
        return None

    def get_setting_value(self, key: str, attr: str, default: Any = None) -> Any:
        """Get a specific attribute from a setting, with extra-field support."""
        for s in self.settings:
            if s.key == key:
                # Check model fields first, then extra fields
                if hasattr(s, attr):
                    return getattr(s, attr, default)
                # Pydantic v2 extra fields
                extras = s.model_extra or {}
                return extras.get(attr, default)
        return default
