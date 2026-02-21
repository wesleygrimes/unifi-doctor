"""UDM Settings Audit — controller/gateway configuration analysis."""

from __future__ import annotations

from unifi_doctor.analysis import rules
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import Finding, Severity, Topology

MODULE = "settings-audit"


def analyze(snapshot: NetworkSnapshot, topology: Topology) -> list[Finding]:
    findings: list[Finding] = []

    # ------- 1. IDS/IPS (Threat Management) -------
    ips_mode = snapshot.get_setting_value("ips", "ips_mode", "")
    if not ips_mode:
        # Try alternate key names
        ips_mode = snapshot.get_setting_value("threat_management", "mode", "")

    if ips_mode and ips_mode.lower() in ("ids", "ips"):
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                module=MODULE,
                title=f"IDS/IPS is ENABLED (mode: {ips_mode.upper()})",
                detail=(
                    f"Threat Management is set to {ips_mode.upper()} mode. On a UDM Pro with "
                    f"1 Gbps fiber, this is almost certainly causing your streaming issues. "
                    f"The UDM Pro's IDS/IPS engine maxes out around {rules.UDM_PRO_IDS_MAX_THROUGHPUT_MBPS} Mbps "
                    "and causes packet drops, latency spikes, and intermittent buffering under load. "
                    "This is the #1 most common cause of streaming failures on UDM Pro."
                ),
                recommendation=(
                    "DISABLE Threat Management entirely, or at minimum switch to IDS-only mode "
                    "(which still has overhead but doesn't drop packets). Test streaming immediately "
                    "after disabling — this alone may fix your issues."
                ),
                ui_path="Settings > Security > Internet Threat Management",
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="IDS/IPS is disabled",
                detail="Good — Threat Management is off, no throughput penalty on your 1 Gbps connection.",
                recommendation="",
            )
        )

    # ------- 2. Smart Queues (SQM / QoS) -------
    sqm_enabled = snapshot.get_setting_value("sqm", "sqm_enabled", False)
    if not sqm_enabled:
        sqm_enabled = snapshot.get_setting_value("smart_queue", "enabled", False)

    if sqm_enabled:
        findings.append(
            Finding(
                severity=Severity.CRITICAL,
                module=MODULE,
                title="Smart Queues (SQM) is ENABLED",
                detail=(
                    "Smart Queues is designed to reduce bufferbloat on slow connections, but "
                    "on a 1 Gbps fiber connection, the UDM Pro cannot process SQM at line rate. "
                    "This adds latency to every packet and can cause throughput to drop to "
                    "~500-700 Mbps. It also consumes significant CPU, leaving less for other "
                    "processing."
                ),
                recommendation=(
                    "DISABLE Smart Queues. On a 1 Gbps fiber connection, bufferbloat is not "
                    "your problem — the fiber link has minimal buffering. SQM is only useful "
                    "on cable/DSL connections under ~300 Mbps."
                ),
                ui_path="Settings > Internet > Advanced > Smart Queues",
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="Smart Queues (SQM) is disabled",
                detail="Good — no unnecessary QoS overhead on your 1 Gbps connection.",
                recommendation="",
            )
        )

    # ------- 3. DPI (Deep Packet Inspection) -------
    dpi_enabled = snapshot.get_setting_value("dpi", "dpi_enabled", False)
    if not dpi_enabled:
        dpi_enabled = snapshot.get_setting_value("dpi", "enabled", False)

    if dpi_enabled:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title="Deep Packet Inspection (DPI) is enabled",
                detail=(
                    "DPI adds CPU overhead by inspecting every packet to classify traffic. "
                    "While less impactful than IDS/IPS, it still consumes resources. The traffic "
                    "identification data is nice-to-have but comes at a performance cost."
                ),
                recommendation=(
                    "Consider disabling DPI if you're experiencing any performance issues. "
                    "The traffic stats aren't worth the overhead if they're contributing to "
                    "streaming problems."
                ),
                ui_path="Settings > Traffic Management > Deep Packet Inspection",
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="DPI is disabled",
                detail="Good — no DPI overhead.",
                recommendation="",
            )
        )

    # ------- 4. DNS settings -------
    dns1 = snapshot.get_setting_value("connectivity", "dns1", "")
    dns2 = snapshot.get_setting_value("connectivity", "dns2", "")

    # Check multiple locations for DNS config
    if not dns1:
        for s in snapshot.settings:
            extras = s.model_extra or {}
            if "dns1" in extras:
                dns1 = extras["dns1"]
                dns2 = extras.get("dns2", "")
                break

    if dns1:
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title=f"DNS servers: {dns1}" + (f", {dns2}" if dns2 else ""),
                detail=(
                    "DNS resolution speed affects how quickly streaming apps can start playing. "
                    "Fast DNS (1.1.1.1, 8.8.8.8) typically resolves in 1-5ms. ISP DNS or "
                    "the UDM's built-in proxy can add 10-50ms."
                ),
                recommendation=(
                    "For best streaming performance, use direct DNS: 1.1.1.1 + 1.0.0.1 "
                    "(Cloudflare) or 8.8.8.8 + 8.8.4.4 (Google). Avoid the UDM as a DNS proxy "
                    "unless you need content filtering."
                ),
                ui_path="Settings > Internet > WAN > DNS Server",
            )
        )

    # ------- 5. UPnP -------
    upnp = snapshot.get_setting_value("upnp", "upnp_enabled", None)
    if upnp is None:
        upnp = snapshot.get_setting_value("upnp", "enabled", None)

    if upnp is True:
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title="UPnP is enabled",
                detail=(
                    "UPnP allows devices to automatically open ports. Some streaming apps and "
                    "game consoles need it. However, it's a security risk as any device on "
                    "the network can open ports."
                ),
                recommendation=(
                    "Leave enabled if you have game consoles or apps that need it. "
                    "If security is a concern, disable and manually forward specific ports."
                ),
                ui_path="Settings > Security > UPnP",
            )
        )
    elif upnp is False:
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title="UPnP is disabled",
                detail="UPnP is off. Some streaming apps may need it for optimal performance.",
                recommendation="If streaming apps report connection issues, consider enabling UPnP.",
                ui_path="Settings > Security > UPnP",
            )
        )

    # ------- 6. Multicast DNS / IGMP snooping -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue

        if not wlan.multicast_enhance:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Multicast Enhancement is OFF",
                    detail=(
                        "Multicast Enhancement (IGMPv3 proxy) converts multicast traffic to "
                        "unicast for wireless clients. Without it, multicast floods the wireless "
                        "network at the lowest data rate, wasting airtime. This is a notorious "
                        "cause of streaming failures on UniFi because mDNS discovery, AirPlay, "
                        "and Chromecast all use multicast."
                    ),
                    recommendation="Enable Multicast Enhancement on this SSID.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > Multicast Enhancement",
                )
            )
        else:
            findings.append(
                Finding(
                    severity=Severity.GOOD,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Multicast Enhancement is ON",
                    detail="Good — multicast is being proxied to unicast for wireless clients.",
                    recommendation="",
                )
            )

        if not wlan.igmp_snooping:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': IGMP Snooping is OFF",
                    detail=(
                        "Without IGMP snooping, multicast traffic is flooded to all ports. "
                        "This wastes bandwidth and can cause congestion."
                    ),
                    recommendation="Enable IGMP Snooping.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > IGMP Snooping",
                )
            )

    # ------- 7. DTIM interval -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue

        # Check both bands
        for band, dtim_val in [("5 GHz", wlan.dtim_na), ("2.4 GHz", wlan.dtim_ng)]:
            if dtim_val > rules.RECOMMENDED_DTIM:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=(
                            f"SSID '{wlan.name}' {band}: DTIM interval is {dtim_val}"
                            f" (should be {rules.RECOMMENDED_DTIM})"
                        ),
                        detail=(
                            f"A DTIM interval of {dtim_val} means clients in power-save mode "
                            f"only wake up every {dtim_val} beacon intervals to check for buffered "
                            "multicast/broadcast frames. This adds latency to streaming apps, "
                            "especially during initial connection and channel changes."
                        ),
                        recommendation=f"Set DTIM to {rules.RECOMMENDED_DTIM} for networks with streaming devices.",
                        ui_path=f"Settings > WiFi > {wlan.name} > Advanced > DTIM Period",
                    )
                )

    # ------- 8. Auto-optimize -------
    auto_opt = snapshot.get_setting_value("auto_optimize", "auto_optimize_enabled", None)
    if auto_opt is None:
        auto_opt = snapshot.get_setting_value("auto_optimize", "enabled", None)

    if auto_opt:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title="Auto-Optimize Network is ENABLED",
                detail=(
                    "Auto-optimize makes periodic, unpredictable changes to channel assignments "
                    "and other radio settings. This can cause sudden, unexplained disconnections "
                    "and performance changes."
                ),
                recommendation=(
                    "DISABLE auto-optimize. Manually configure channels and power using the "
                    "channel plan from this tool. Deterministic settings > random optimization."
                ),
                ui_path="Settings > WiFi > Global AP Settings > Auto-Optimize Network",
            )
        )
    elif auto_opt is False:
        findings.append(
            Finding(
                severity=Severity.GOOD,
                module=MODULE,
                title="Auto-Optimize is disabled",
                detail="Good — channel/radio settings won't change unexpectedly.",
                recommendation="",
            )
        )

    # ------- 9. Connectivity Monitor -------
    conn_host = snapshot.get_setting_value("connectivity", "connectivity_host", "")
    if conn_host and conn_host not in ("1.1.1.1", "8.8.8.8", "8.8.4.4", "1.0.0.1"):
        findings.append(
            Finding(
                severity=Severity.INFO,
                module=MODULE,
                title=f"Connectivity monitor target: {conn_host}",
                detail=(
                    "The connectivity monitor pings this target to determine if WAN is up. "
                    "Using an unreliable target can cause the UDM to think the internet is "
                    "down and trigger failover or other disruptive behavior."
                ),
                recommendation="Set connectivity monitor to 1.1.1.1 or 8.8.8.8 for reliability.",
                ui_path="Settings > Internet > Advanced > Connectivity Monitor",
            )
        )

    # ------- 10. Firmware version check -------
    gateway = snapshot.gateway
    if gateway:
        for buggy in rules.BUGGY_FIRMWARE_PATTERNS:
            if buggy["pattern"] in gateway.version:
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=f"Firmware {gateway.version}: known issues",
                        detail=f"Firmware version {gateway.version} has known issues: {buggy['note']}",
                        recommendation="Update to the latest stable firmware.",
                        ui_path="Settings > System > Updates",
                    )
                )
                break

    # ------- 11. PMF (Protected Management Frames) -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue
        if wlan.pmf_mode == "required":
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': PMF set to Required",
                    detail=(
                        "Required PMF can prevent older devices from connecting. 'Optional' is safer for compatibility."
                    ),
                    recommendation="Set PMF to 'Optional' unless you specifically need it required.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Security > PMF",
                )
            )

    return findings
