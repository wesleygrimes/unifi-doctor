"""Streaming Diagnosis — targeted analysis for 'why can't my wife stream?'"""

from __future__ import annotations

from unifi_doctor.analysis import rules
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import ClientInfo, Finding, Severity, Topology

MODULE = "streaming-diagnosis"


def _is_streaming_device(client: ClientInfo) -> tuple[bool, str]:
    """Determine if a client is likely a streaming device. Returns (is_streaming, vendor)."""
    mac_upper = client.mac.upper()

    # Check OUI
    oui_prefix = mac_upper[:8]
    if oui_prefix in rules.STREAMING_DEVICE_OUIS:
        return True, rules.STREAMING_DEVICE_OUIS[oui_prefix]

    # Check hostname keywords
    hostname = (client.hostname or client.name or "").lower()
    for kw in rules.STREAMING_HOSTNAME_KEYWORDS:
        if kw in hostname:
            return True, f"hostname match: {kw}"

    # Check OUI field from the API
    oui = (client.oui or "").lower()
    streaming_oui_keywords = [
        "amazon",
        "roku",
        "apple",
        "google",
        "samsung",
        "lg",
        "sony",
        "sonos",
        "nvidia",
        "tivo",
    ]
    for kw in streaming_oui_keywords:
        if kw in oui:
            return True, oui

    return False, ""


def analyze(snapshot: NetworkSnapshot, topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    aps = snapshot.aps

    # ------- 1. Identify streaming devices -------
    streaming_devices: list[tuple[ClientInfo, str]] = []
    for client in snapshot.clients:
        is_stream, vendor = _is_streaming_device(client)
        if is_stream:
            streaming_devices.append((client, vendor))

    if not streaming_devices:
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title="No streaming devices detected",
                detail=(
                    "Could not identify any streaming devices (smart TVs, Fire Sticks, "
                    "Apple TV, Roku, Chromecast) by MAC address or hostname. They may be "
                    "offline or using an unrecognized MAC."
                ),
                recommendation=(
                    "Check if streaming devices are powered on. If using private/randomized "
                    "MAC addresses, look in the UniFi client list for devices you recognize."
                ),
            )
        )
        # Still check settings that affect streaming
    else:
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title=f"Found {len(streaming_devices)} likely streaming device(s)",
                detail=", ".join(f"{c.display_name} ({vendor})" for c, vendor in streaming_devices),
                recommendation="",
            )
        )

    # ------- 2. Per-device analysis -------
    for client, vendor in streaming_devices:
        ap_name = next(
            (a.display_name for a in aps if a.mac == client.ap_mac),
            client.ap_mac or "unknown",
        )
        rssi = client.rssi or client.signal

        # Signal strength
        if rssi and rssi < -72:
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    module=MODULE,
                    title=f"{client.display_name} ({vendor}): Weak signal ({rssi} dBm) on {ap_name}",
                    detail=(
                        f"This streaming device has a signal of {rssi} dBm, which is too weak "
                        "for reliable video streaming. Expect buffering, quality drops, and "
                        "timeouts, especially for 4K content."
                    ),
                    recommendation=(
                        "Move the device closer to an AP, add an AP closer to this device, "
                        "or check for obstructions. Signal should be -65 dBm or better for "
                        "reliable 4K streaming."
                    ),
                )
            )
        elif rssi and rssi < -65:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{client.display_name} ({vendor}): Marginal signal ({rssi} dBm)",
                    detail=(
                        f"Signal of {rssi} dBm is workable for HD streaming but may struggle "
                        "with 4K or during peak congestion."
                    ),
                    recommendation="Consider AP placement to improve coverage for this device.",
                )
            )
        elif rssi:
            findings.append(
                Finding(
                    severity=Severity.GOOD,
                    module=MODULE,
                    title=f"{client.display_name} ({vendor}): Good signal ({rssi} dBm) on {ap_name}",
                    detail="Signal strength is adequate for streaming.",
                    recommendation="",
                )
            )

        # Band check — 2.4 GHz is bad for streaming
        if client.is_2g:
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    module=MODULE,
                    title=f"{client.display_name} ({vendor}): Connected on 2.4 GHz (channel {client.channel})",
                    detail=(
                        "This streaming device is on the 2.4 GHz band. 2.4 GHz has much less "
                        "bandwidth, more interference (microwaves, Bluetooth, every neighbor's "
                        "WiFi), and higher latency than 5 GHz. This alone can cause buffering "
                        "and quality issues on streaming apps."
                    ),
                    recommendation=(
                        "Force this device to 5 GHz if it supports it. Check band steering "
                        "settings. If the device is too far from the AP for 5 GHz, you need "
                        "a closer AP."
                    ),
                )
            )
        elif client.is_5g:
            findings.append(
                Finding(
                    severity=Severity.GOOD,
                    module=MODULE,
                    title=f"{client.display_name} ({vendor}): On 5 GHz (channel {client.channel})",
                    detail="Good — connected on the faster 5 GHz band.",
                    recommendation="",
                )
            )

        # TX/RX rate
        tx = rules.normalize_rate_mbps(client.tx_rate)
        rx = rules.normalize_rate_mbps(client.rx_rate)
        rate = min(tx, rx) if tx and rx else (tx or rx)

        if rate and rate < 50:
            findings.append(
                Finding(
                    severity=Severity.CRITICAL,
                    module=MODULE,
                    title=f"{client.display_name}: PHY rate only {rate} Mbps",
                    detail=(
                        f"A PHY rate of {rate} Mbps means real-world throughput is likely "
                        "under 25 Mbps. 4K streaming requires 25+ Mbps sustained. "
                        "This device will buffer."
                    ),
                    recommendation="Improve signal or move to 5 GHz.",
                )
            )
        elif rate and rate < 100:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{client.display_name}: PHY rate is {rate} Mbps",
                    detail="Marginal for 4K streaming. HD should work but may have occasional issues.",
                    recommendation="Check signal strength and interference.",
                )
            )

    # ------- 3. Recent disconnect events for streaming devices -------
    streaming_macs = {c.mac.lower() for c, _ in streaming_devices}
    disconnect_events = [
        e
        for e in snapshot.events
        if e.user
        and e.user.lower() in streaming_macs
        and any(kw in e.key.lower() for kw in ("disconnect", "reconnect", "deauth"))
    ]

    if disconnect_events:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title=f"{len(disconnect_events)} disconnect events for streaming devices",
                detail=(
                    "Recent disconnect/reconnect events for your streaming devices:\n"
                    + "\n".join(
                        f"  - {e.timestamp.strftime('%m/%d %H:%M')}: {e.msg or e.key}" for e in disconnect_events[:10]
                    )
                ),
                recommendation=(
                    "Frequent disconnects point to roaming issues, interference, or "
                    "min RSSI kicking clients off. Check 802.11r/v/k settings and "
                    "min RSSI thresholds."
                ),
            )
        )

    # ------- 4. Multicast / IGMP / DTIM settings -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue

        issues = []
        if not wlan.multicast_enhance:
            issues.append("Multicast Enhancement OFF")
        if not wlan.igmp_snooping:
            issues.append("IGMP Snooping OFF")
        if wlan.dtim_na > 1 or wlan.dtim_ng > 1:
            issues.append(f"DTIM interval is {max(wlan.dtim_na, wlan.dtim_ng)} (should be 1)")

        if issues:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Streaming-hostile settings detected",
                    detail=(
                        f"The following settings on SSID '{wlan.name}' are known to cause "
                        f"streaming problems: {', '.join(issues)}. Bad multicast handling is "
                        "a notorious cause of streaming failures on UniFi."
                    ),
                    recommendation=("Enable Multicast Enhancement, enable IGMP Snooping, and set DTIM interval to 1."),
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced",
                )
            )

    # ------- 5. Narrative summary -------
    critical_count = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    warning_count = sum(1 for f in findings if f.severity == Severity.WARNING)

    if critical_count > 0:
        narrative_parts = []
        for f in findings:
            if f.severity == Severity.CRITICAL:
                narrative_parts.append(f"• {f.title}")

        findings.insert(
            0,
            Finding(
                severity=Severity.CRITICAL,
                module=MODULE,
                title=f"STREAMING DIAGNOSIS: {critical_count} critical issue(s) found",
                detail=(
                    "Here's probably why streaming is breaking:\n"
                    + "\n".join(narrative_parts)
                    + "\n\nFix these in order — start with IDS/IPS if it's on, then address "
                    "signal/band issues for specific devices."
                ),
                recommendation="See individual findings below for exact fix instructions.",
            ),
        )
    elif warning_count > 0:
        findings.insert(
            0,
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title=f"STREAMING DIAGNOSIS: {warning_count} potential issue(s)",
                detail="No critical problems found, but several warnings that could contribute to intermittent issues.",
                recommendation="Address warnings in order of severity.",
            ),
        )
    else:
        findings.insert(
            0,
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="STREAMING DIAGNOSIS: No obvious issues detected",
                detail=(
                    "Network configuration looks reasonable for streaming. If you're still "
                    "having issues, they may be ISP-side or app-specific."
                ),
                recommendation=(
                    "Try: power-cycle streaming devices, check ISP for outages, test with "
                    "a wired connection to rule out WiFi."
                ),
            ),
        )

    return findings
