"""Shared test fixtures and factories."""

from __future__ import annotations

from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import (
    ClientInfo,
    DeviceInfo,
    RadioTableEntry,
    RadioTableStatsEntry,
    UplinkInfo,
    WLANConfig,
)


def make_ap(
    mac="aa:bb:cc:dd:ee:01",
    name="Test-AP",
    ch_2g=1,
    ch_5g=36,
    ht_2g=20,
    ht_5g=40,
    uplink_speed=1000,
) -> DeviceInfo:
    return DeviceInfo(
        mac=mac,
        name=name,
        type="uap",
        model="U6-LR",
        radio_table=[
            RadioTableEntry(radio="ng", channel=ch_2g, ht=ht_2g, tx_power_mode="medium"),
            RadioTableEntry(radio="na", channel=ch_5g, ht=ht_5g, tx_power_mode="medium"),
        ],
        radio_table_stats=[
            RadioTableStatsEntry(name="ra0", channel=ch_2g, cu_total=10),
            RadioTableStatsEntry(name="rai0", channel=ch_5g, cu_total=15),
        ],
        uplink=UplinkInfo(type="wire", speed=uplink_speed),
    )


def make_client(
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
    )


def make_wlan(
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
    wlan_id="",
) -> WLANConfig:
    kwargs = dict(
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
    if wlan_id:
        kwargs["id"] = wlan_id
    return WLANConfig(**kwargs)


def make_gateway(mac="aa:bb:cc:dd:ee:ff", version="7.1.0") -> DeviceInfo:
    return DeviceInfo(mac=mac, name="UDM-Pro", type="udm", model="UDM-Pro", version=version)


def make_snapshot(
    devices=None,
    clients=None,
    rogue_aps=None,
    wlan_configs=None,
    settings=None,
    health=None,
    events=None,
) -> NetworkSnapshot:
    return NetworkSnapshot(
        devices=devices or [],
        clients=clients or [],
        rogue_aps=rogue_aps or [],
        wlan_configs=wlan_configs or [],
        settings=settings or [],
        health=health or [],
        events=events or [],
    )
