"""RF Analysis — channel overlap, utilization, power, interference, channel plan."""

from __future__ import annotations

from unifi_doctor.analysis import rules
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import (
    Band,
    ChannelPlan,
    DeviceInfo,
    Finding,
    FloorLevel,
    Severity,
    Topology,
)

MODULE = "rf-analysis"


def _parse_channel(ch: int | str) -> int:
    """Safely parse channel to int."""
    try:
        return int(ch)
    except (ValueError, TypeError):
        return 0


def _get_radio_stats(ap: DeviceInfo, band: str) -> dict:
    """Get radio stats for a band (ra0=2g or rai0/ra1=5g typically)."""
    for rs in ap.radio_table_stats:
        ch = _parse_channel(rs.channel)
        if band == "2g" and 0 < ch <= 14:
            return rs.model_dump()
        if band == "5g" and ch > 14:
            return rs.model_dump()
    # Fallback: check radio_table
    for rt in ap.radio_table:
        if band == "2g" and rt.radio in ("ng", "ra0"):
            return rt.model_dump()
        if band == "5g" and rt.radio in ("na", "rai0", "ra1"):
            return rt.model_dump()
    return {}


def _get_radio_config(ap: DeviceInfo, band: str) -> dict:
    """Get radio config entry for a band."""
    for rt in ap.radio_table:
        ch = _parse_channel(rt.channel)
        if band == "2g" and (rt.radio in ("ng", "ra0") or 0 < ch <= 14):
            return rt.model_dump()
        if band == "5g" and (rt.radio in ("na", "rai0", "ra1") or ch > 14):
            return rt.model_dump()
    return {}


def analyze(snapshot: NetworkSnapshot, topology: Topology) -> tuple[list[Finding], list[ChannelPlan]]:
    """Run full RF analysis, return findings and a recommended channel plan."""
    findings: list[Finding] = []
    channel_plan: list[ChannelPlan] = []
    aps = snapshot.aps

    if not aps:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title="No APs found",
                detail="No access points were discovered. Cannot perform RF analysis.",
                recommendation="Ensure APs are adopted and online.",
            )
        )
        return findings, channel_plan

    # Build placement lookup
    placement_map = {p.mac: p for p in topology.placements}
    link_map: dict[tuple[str, str], float] = {}
    for link in topology.links:
        link_map[(link.ap1_mac, link.ap2_mac)] = link.distance_ft
        link_map[(link.ap2_mac, link.ap1_mac)] = link.distance_ft

    # Collect per-AP channel info
    ap_channels_2g: dict[str, int] = {}
    ap_channels_5g: dict[str, int] = {}
    ap_widths_5g: dict[str, int] = {}
    ap_widths_2g: dict[str, int] = {}

    for ap in aps:
        cfg_2g = _get_radio_config(ap, "2g")
        cfg_5g = _get_radio_config(ap, "5g")
        stats_2g = _get_radio_stats(ap, "2g")
        stats_5g = _get_radio_stats(ap, "5g")

        ch_2g = _parse_channel(stats_2g.get("channel") or cfg_2g.get("channel", 0))
        ch_5g = _parse_channel(stats_5g.get("channel") or cfg_5g.get("channel", 0))

        if ch_2g:
            ap_channels_2g[ap.mac] = ch_2g
        if ch_5g:
            ap_channels_5g[ap.mac] = ch_5g

        ap_widths_2g[ap.mac] = cfg_2g.get("ht", 20)
        ap_widths_5g[ap.mac] = cfg_5g.get("ht", 40)

    # ------- 1. Invalid 2.4 GHz channels -------
    for ap in aps:
        ch = ap_channels_2g.get(ap.mac, 0)
        if ch and not rules.is_valid_24g_channel(ch):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{ap.display_name}: Invalid 2.4 GHz channel {ch}",
                    detail=(
                        f"Channel {ch} on 2.4 GHz is not one of the three non-overlapping channels. "
                        "Using non-standard channels causes overlap with neighboring channels and "
                        "increases interference for everyone."
                    ),
                    recommendation="Change to channel 1, 6, or 11.",
                    ui_path=f"UniFi > Devices > {ap.display_name} > Settings > Radios > 2.4 GHz > Channel",
                )
            )

    # ------- 2. 2.4 GHz channel width -------
    for ap in aps:
        w = ap_widths_2g.get(ap.mac, 20)
        if w > 20:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{ap.display_name}: 2.4 GHz width is {w} MHz (should be 20)",
                    detail=(
                        "Channel widths above 20 MHz on 2.4 GHz cause massive overlap with "
                        "neighboring channels. There are only 3 non-overlapping 20 MHz channels."
                    ),
                    recommendation="Set 2.4 GHz channel width to 20 MHz (HT20).",
                    ui_path=f"Devices > {ap.display_name} > Settings > Radios > 2.4 GHz > Channel Width",
                )
            )

    # ------- 3. Duplicate 5 GHz channels -------
    ch_to_aps_5g: dict[int, list[str]] = {}
    for mac, ch in ap_channels_5g.items():
        ch_to_aps_5g.setdefault(ch, []).append(mac)

    for ch, macs in ch_to_aps_5g.items():
        if len(macs) > 1:
            names = [next((a.display_name for a in aps if a.mac == m), m) for m in macs]
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    module=MODULE,
                    title=f"5 GHz channel {ch} shared by {len(macs)} APs",
                    detail=(
                        f"APs {', '.join(names)} are all on 5 GHz channel {ch}. "
                        "This causes co-channel interference (CCI) and dramatically "
                        "reduces throughput for clients on all of these APs."
                    ),
                    recommendation=(
                        "Assign unique, non-overlapping 5 GHz channels to each AP. See the channel plan below."
                    ),
                    ui_path="Devices > [AP] > Settings > Radios > 5 GHz > Channel",
                )
            )

    # ------- 4. Adjacent/overlapping 5 GHz channels -------
    ap_macs = list(ap_channels_5g.keys())
    for i in range(len(ap_macs)):
        for j in range(i + 1, len(ap_macs)):
            m1, m2 = ap_macs[i], ap_macs[j]
            ch1, ch2 = ap_channels_5g[m1], ap_channels_5g[m2]
            w1, w2 = ap_widths_5g.get(m1, 40), ap_widths_5g.get(m2, 40)
            if ch1 != ch2 and rules.channels_overlap_5g(ch1, ch2, w1, w2):
                n1 = next((a.display_name for a in aps if a.mac == m1), m1)
                n2 = next((a.display_name for a in aps if a.mac == m2), m2)
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=f"5 GHz channel overlap: {n1} (ch{ch1}/{w1}MHz) ↔ {n2} (ch{ch2}/{w2}MHz)",
                        detail="These channels overlap at the configured widths, causing interference.",
                        recommendation="Use non-overlapping channels or reduce channel width to 40 MHz.",
                    )
                )

    # ------- 5. Channel utilization -------
    for ap in aps:
        for band_label, band_key in [("2.4 GHz", "2g"), ("5 GHz", "5g")]:
            stats = _get_radio_stats(ap, band_key)
            cu = stats.get("cu_total", 0)
            if cu > rules.CHANNEL_UTIL_WARNING_PCT:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=f"{ap.display_name}: {band_label} channel utilization at {cu}%",
                        detail=(
                            f"Channel utilization above {rules.CHANNEL_UTIL_WARNING_PCT}% means the "
                            "airtime is congested. Clients will experience delays and retransmissions."
                        ),
                        recommendation=(
                            "Consider changing channels, reducing channel width, or lowering TX power "
                            "to reduce self-interference."
                        ),
                    )
                )

    # ------- 6. Noise floor -------
    for ap in aps:
        for band_label, band_key in [("2.4 GHz", "2g"), ("5 GHz", "5g")]:
            stats = _get_radio_stats(ap, band_key)
            nf = stats.get("noise_floor", -100)
            if nf > rules.NOISE_FLOOR_WARNING_DBM:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=f"{ap.display_name}: {band_label} noise floor is {nf} dBm",
                        detail=(
                            f"A noise floor above {rules.NOISE_FLOOR_WARNING_DBM} dBm indicates "
                            "significant RF interference from non-WiFi sources (microwaves, Bluetooth, "
                            "baby monitors, etc.)."
                        ),
                        recommendation=("Identify and relocate interference sources. Consider changing channels."),
                    )
                )

    # ------- 7. Neighbor interference analysis -------
    neighbor_channels_2g: dict[int, int] = {}
    neighbor_channels_5g: dict[int, int] = {}
    for rogue in snapshot.rogue_aps:
        ch = _parse_channel(rogue.channel)
        if 0 < ch <= 14:
            neighbor_channels_2g[ch] = neighbor_channels_2g.get(ch, 0) + 1
        elif ch > 14:
            neighbor_channels_5g[ch] = neighbor_channels_5g.get(ch, 0) + 1

    total_neighbors = sum(neighbor_channels_2g.values()) + sum(neighbor_channels_5g.values())
    if total_neighbors > 0:
        # Report most congested channels
        for ch, count in sorted(neighbor_channels_2g.items(), key=lambda x: -x[1])[:3]:
            if count >= 5:
                findings.append(
                    Finding(
                        severity=Severity.INFO,
                        module=MODULE,
                        title=f"2.4 GHz channel {ch}: {count} neighboring networks detected",
                        detail="Heavy neighbor presence on this channel increases contention.",
                        recommendation=f"Avoid channel {ch} on 2.4 GHz if possible.",
                    )
                )

    # ------- 8. 5 GHz channel width check -------
    for ap in aps:
        w = ap_widths_5g.get(ap.mac, 40)
        if w >= 80 and total_neighbors > rules.MAX_NEIGHBORS_FOR_80MHZ:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{ap.display_name}: 5 GHz using {w} MHz width with many neighbors",
                    detail=(
                        f"80 MHz channels use more spectrum and are more likely to overlap "
                        f"with the {total_neighbors} neighboring networks detected. "
                        "40 MHz is more reliable in most home environments."
                    ),
                    recommendation="Reduce 5 GHz channel width to 40 MHz (VHT40).",
                    ui_path=f"Devices > {ap.display_name} > Settings > Radios > 5 GHz > Channel Width",
                )
            )

    # ------- 9. 2.4 GHz power too high -------
    for ap in aps:
        cfg = _get_radio_config(ap, "2g")
        power_mode = cfg.get("tx_power_mode", "auto")
        tx_power = cfg.get("tx_power", 0)
        if power_mode == "high" or (power_mode == "custom" and tx_power > 17):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{ap.display_name}: 2.4 GHz power is too high ({power_mode}, {tx_power} dBm)",
                    detail=(
                        "High 2.4 GHz power causes asymmetric links — clients hear the AP fine "
                        "but can't transmit back as loudly. This leads to poor performance and "
                        "sticky clients that won't roam."
                    ),
                    recommendation="Set 2.4 GHz TX power to Low or Medium.",
                    ui_path=f"Devices > {ap.display_name} > Settings > Radios > 2.4 GHz > Transmit Power",
                )
            )

    # ------- 10. Generate channel plan -------
    # Check for radar events to decide on DFS
    has_radar = any("radar" in e.key.lower() or "radar" in e.msg.lower() for e in snapshot.events)
    neighbor_5g_set = set(neighbor_channels_5g.keys())

    rec_5g_channels = rules.get_recommended_5g_channels(
        len(aps), has_radar_events=has_radar, neighbor_channels=neighbor_5g_set
    )
    rec_2g_channels = rules.get_recommended_24g_channels(len(aps))

    for i, ap in enumerate(aps):
        placement = placement_map.get(ap.mac)
        is_outdoor = placement and placement.floor == FloorLevel.DETACHED

        # 2.4 GHz plan
        current_2g = ap_channels_2g.get(ap.mac, 0)
        rec_2g = rec_2g_channels[i] if i < len(rec_2g_channels) else 1
        cfg_2g = _get_radio_config(ap, "2g")

        channel_plan.append(
            ChannelPlan(
                ap_mac=ap.mac,
                ap_name=ap.display_name,
                band=Band.BAND_2G,
                current_channel=current_2g,
                recommended_channel=rec_2g,
                current_width=ap_widths_2g.get(ap.mac, 20),
                recommended_width=20,
                current_power=cfg_2g.get("tx_power_mode", "auto"),
                recommended_power=rules.RECOMMENDED_24G_POWER,
                reason="2.4 GHz: channel 1/6/11, 20 MHz width, low power",
            )
        )

        # 5 GHz plan
        current_5g = ap_channels_5g.get(ap.mac, 0)
        rec_5g = rec_5g_channels[i] if i < len(rec_5g_channels) else 36
        cfg_5g = _get_radio_config(ap, "5g")

        rec_power = rules.RECOMMENDED_5G_OUTDOOR_POWER if is_outdoor else rules.RECOMMENDED_5G_INDOOR_POWER

        channel_plan.append(
            ChannelPlan(
                ap_mac=ap.mac,
                ap_name=ap.display_name,
                band=Band.BAND_5G,
                current_channel=current_5g,
                recommended_channel=rec_5g,
                current_width=ap_widths_5g.get(ap.mac, 40),
                recommended_width=rules.RECOMMENDED_5G_WIDTH_DEFAULT,
                current_power=cfg_5g.get("tx_power_mode", "auto"),
                recommended_power=rec_power,
                reason=(
                    f"5 GHz: non-overlapping, "
                    f"{'DFS preferred' if not has_radar else 'non-DFS (radar detected)'}, "
                    f"{rec_power} power"
                ),
            )
        )

    # ------- Mark good things -------
    all_2g_valid = all(rules.is_valid_24g_channel(ch) for ch in ap_channels_2g.values() if ch)
    if all_2g_valid and ap_channels_2g:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="All 2.4 GHz channels are valid (1, 6, or 11)",
                detail="Good — using only non-overlapping channels on 2.4 GHz.",
                recommendation="",
            )
        )

    unique_5g = len(set(ap_channels_5g.values())) == len(ap_channels_5g) if ap_channels_5g else False
    if unique_5g and len(ap_channels_5g) > 1:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="All 5 GHz channels are unique across APs",
                detail="Good — no co-channel interference between your APs on 5 GHz.",
                recommendation="",
            )
        )

    return findings, channel_plan
