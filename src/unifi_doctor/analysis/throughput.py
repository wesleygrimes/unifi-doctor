"""Throughput Analysis — PHY rates, legacy devices, uplink verification, mesh detection."""

from __future__ import annotations

from unifi_doctor.analysis import rules
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import Finding, Severity, Topology

MODULE = "throughput-analysis"


def analyze(snapshot: NetworkSnapshot, topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    aps = snapshot.aps

    # ------- 1. Per-client TX/RX rates on 5 GHz -------
    poor_rate_clients = []
    for client in snapshot.clients:
        if client.is_wired:
            continue
        if not client.is_5g:
            continue

        tx = rules.normalize_rate_mbps(client.tx_rate)
        rx = rules.normalize_rate_mbps(client.rx_rate)

        rate = min(tx, rx) if tx and rx else (tx or rx)
        if rate and rate < rules.POOR_5G_PHY_RATE_MBPS:
            ap_name = next(
                (a.display_name for a in aps if a.mac == client.ap_mac),
                client.ap_mac,
            )
            poor_rate_clients.append((client, rate, ap_name))

    if poor_rate_clients:
        for client, rate, ap_name in poor_rate_clients[:10]:  # Cap at 10
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"{client.display_name}: 5 GHz PHY rate only {rate} Mbps",
                    detail=(
                        f"Client '{client.display_name}' ({client.mac}) on AP '{ap_name}' "
                        f"has a PHY rate of {rate} Mbps on 5 GHz. Below {rules.POOR_5G_PHY_RATE_MBPS} Mbps "
                        "indicates the client is either too far away, experiencing heavy "
                        "interference, or using outdated WiFi hardware."
                    ),
                    recommendation=(
                        "Check client distance to AP. If signal is weak (< -72 dBm), the client "
                        "needs a closer AP or the AP power needs adjustment."
                    ),
                )
            )

    if not poor_rate_clients and any(c.is_5g and not c.is_wired for c in snapshot.clients):
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="All 5 GHz clients have acceptable PHY rates",
                detail=f"No wireless clients below {rules.POOR_5G_PHY_RATE_MBPS} Mbps on 5 GHz.",
                recommendation="",
            )
        )

    # ------- 2. Legacy device detection -------
    legacy_clients = []
    for client in snapshot.clients:
        if client.is_wired:
            continue
        proto = client.radio_proto.lower() if client.radio_proto else ""
        # Check for legacy protocols
        if proto in ("b", "g", "a"):
            legacy_clients.append((client, proto))
        elif proto == "n" and client.is_2g:
            # 802.11n on 2.4 GHz is borderline — note but less severe
            pass

    if legacy_clients:
        for client, proto in legacy_clients:
            ap_name = next(
                (a.display_name for a in aps if a.mac == client.ap_mac),
                client.ap_mac,
            )
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"Legacy device: {client.display_name} using 802.11{proto}",
                    detail=(
                        f"Client '{client.display_name}' ({client.mac}) is using 802.11{proto}, "
                        f"a legacy protocol. Connected to AP '{ap_name}'. Legacy devices force "
                        "the AP to use protection mechanisms that slow down ALL clients on that "
                        "AP, not just the legacy device."
                    ),
                    recommendation=(
                        "Consider replacing this device, connecting it via Ethernet, or "
                        "isolating it on a separate SSID with a lower data rate. If it's an "
                        "IoT device, a dedicated 2.4 GHz IoT network can contain the impact."
                    ),
                )
            )

    # ------- 3. AP uplink verification -------
    for ap in aps:
        uplink_type = ap.uplink_type or (ap.uplink.type if ap.uplink else "")

        # Check wired uplink speed
        if uplink_type == "wire" or not uplink_type:
            speed = ap.uplink.speed if ap.uplink else 0
            if speed and speed < rules.EXPECTED_UPLINK_SPEED_MBPS:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=(
                            f"{ap.display_name}: Uplink at {speed} Mbps (expected {rules.EXPECTED_UPLINK_SPEED_MBPS})"
                        ),
                        detail=(
                            f"AP '{ap.display_name}' has a wired uplink running at only {speed} Mbps. "
                            "This bottlenecks all clients on this AP. Common causes: Cat5 cable "
                            "(instead of Cat5e/6), bad cable termination, or port negotiation issue."
                        ),
                        recommendation=(
                            "Check the Ethernet cable — replace with Cat6 if needed. Verify both "
                            "ends are properly terminated. Check switch port settings."
                        ),
                    )
                )

            # Check port errors
            for port in ap.port_table:
                if port.up and (port.rx_errors > 100 or port.tx_errors > 100):
                    findings.append(
                        Finding(
                            severity=Severity.WARNING,
                            module=MODULE,
                            title=f"{ap.display_name} port {port.port_idx}: {port.rx_errors + port.tx_errors} errors",
                            detail=(
                                f"Port {port.port_idx} on {ap.display_name} has accumulated "
                                f"{port.rx_errors} RX and {port.tx_errors} TX errors. "
                                "This indicates cable problems or port issues."
                            ),
                            recommendation=(
                                "Replace the Ethernet cable. If errors persist, try a different switch port."
                            ),
                        )
                    )

    # ------- 4. Mesh detection -------
    mesh_aps = []
    for ap in aps:
        is_mesh = (
            ap.uplink_type == "wireless" or ap.mesh_sta_vap_enabled or (ap.uplink and ap.uplink.type == "wireless")
        )
        if is_mesh:
            mesh_aps.append(ap)

    for ap in mesh_aps:
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                module=MODULE,
                title=f"{ap.display_name}: Running on WIRELESS MESH uplink",
                detail=(
                    f"AP '{ap.display_name}' is using a wireless mesh backhaul instead of "
                    "Ethernet. This HALVES the available bandwidth (the AP uses the same "
                    "radio for backhaul and client service) and adds 2-10ms latency per hop. "
                    "For streaming, this is a major bottleneck."
                ),
                recommendation=(
                    "Run Ethernet to this AP if at all possible. Even a single mesh hop "
                    "dramatically degrades throughput and latency. If Ethernet isn't feasible, "
                    "consider MoCA adapters over coax or powerline as alternatives."
                ),
                ui_path=f"Devices > {ap.display_name} > Details > Uplink",
            )
        )

    if not mesh_aps and aps:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="All APs are wired (no mesh)",
                detail="Good — all APs have wired Ethernet backhaul for maximum throughput.",
                recommendation="",
            )
        )

    # ------- 5. Client band distribution -------
    wireless_clients = [c for c in snapshot.clients if not c.is_wired]
    clients_2g = [c for c in wireless_clients if c.is_2g]
    clients_5g = [c for c in wireless_clients if c.is_5g]

    if wireless_clients:
        pct_5g = len(clients_5g) / len(wireless_clients) * 100
        if pct_5g < 50:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    module=MODULE,
                    title=(
                        f"Only {pct_5g:.0f}% of wireless clients on 5 GHz ({len(clients_5g)}/{len(wireless_clients)})"
                    ),
                    detail=(
                        f"{len(clients_2g)} clients are on 2.4 GHz. While some IoT devices "
                        "require 2.4 GHz, phones, laptops, and streaming devices should be on 5 GHz "
                        "for better performance."
                    ),
                    recommendation=(
                        "Enable 'Prefer 5G' band steering. Check that 5 GHz coverage is adequate in all areas."
                    ),
                )
            )

    return findings
