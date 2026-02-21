"""Roaming Analysis — sticky clients, roaming storms, 802.11r/v/k, min RSSI, band steering."""

from __future__ import annotations

from collections import Counter

from unifi_doctor.analysis import rules
from unifi_doctor.api.client import NetworkSnapshot
from unifi_doctor.models.types import Finding, Severity, Topology

MODULE = "roaming-analysis"


def analyze(snapshot: NetworkSnapshot, topology: Topology) -> list[Finding]:
    findings: list[Finding] = []
    aps = snapshot.aps

    if not aps:
        return findings

    # ------- 1. Sticky clients (poor signal but connected to far AP) -------
    for client in snapshot.clients:
        if client.is_wired:
            continue
        rssi = client.rssi or client.signal
        if rssi and rssi < rules.STICKY_CLIENT_RSSI_THRESHOLD and rssi != 0:
            ap_name = next(
                (a.display_name for a in aps if a.mac == client.ap_mac),
                client.ap_mac,
            )
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"Sticky client: {client.display_name} at {rssi} dBm on {ap_name}",
                    detail=(
                        f"Client '{client.display_name}' ({client.mac}) is connected to "
                        f"AP '{ap_name}' with a signal of {rssi} dBm, which is below the "
                        f"-72 dBm threshold. This client should be roaming to a closer AP."
                    ),
                    recommendation=(
                        "Enable minimum RSSI on APs to kick weak clients. "
                        "Enable 802.11r/v/k for faster roaming. "
                        "Check if the closer AP has capacity."
                    ),
                )
            )

    # ------- 2. Roaming event analysis (bounce detection) -------
    roam_events = [e for e in snapshot.events if any(kw in e.key.lower() for kw in ("roam", "connect", "disconnect"))]

    # Count roams per client MAC
    client_roam_counts: Counter[str] = Counter()
    for evt in roam_events:
        if evt.user:
            client_roam_counts[evt.user] += 1

    # Approximate: events span varies, normalize to per-hour
    # If we have 500 events max, estimate time window from first/last
    if roam_events:
        times = [e.time for e in roam_events if e.time]
        if len(times) >= 2:
            window_hours = max((max(times) - min(times)) / 3600, 1)
        else:
            window_hours = 1

        for client_mac, count in client_roam_counts.most_common(20):
            rate = count / window_hours
            if rate > rules.ROAM_EVENTS_PER_HOUR_THRESHOLD:
                client_name = next(
                    (c.display_name for c in snapshot.clients if c.mac == client_mac),
                    client_mac,
                )
                findings.append(
                    Finding(
                        severity=Severity.WARNING,
                        module=MODULE,
                        title=f"Roaming storm: {client_name} — {rate:.1f} roams/hour",
                        detail=(
                            f"Client '{client_name}' ({client_mac}) is bouncing between APs "
                            f"at {rate:.1f} events/hour (threshold: {rules.ROAM_EVENTS_PER_HOUR_THRESHOLD}). "
                            "This causes repeated connection drops and latency spikes."
                        ),
                        recommendation=(
                            "Check AP power levels — overlapping coverage causes ping-pong. "
                            "Enable 802.11v (BSS Transition) so APs can direct clients. "
                            "Consider adjusting min RSSI thresholds to create cleaner cell boundaries."
                        ),
                    )
                )

    # ------- 3. 802.11r/v/k status -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue

        if not wlan.fast_roaming_enabled:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': 802.11r (Fast Roaming) is disabled",
                    detail=(
                        "802.11r (Fast BSS Transition) allows clients to pre-authenticate "
                        "with the target AP before roaming, reducing handoff time from ~400ms "
                        "to ~50ms. This prevents the brief dropout that kills streaming."
                    ),
                    recommendation="Enable Fast Roaming (802.11r) on this SSID.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > Fast Roaming",
                )
            )
        else:
            findings.append(
                Finding(
                    severity=Severity.GOOD,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': 802.11r (Fast Roaming) is enabled",
                    detail="Good — clients can perform fast BSS transitions.",
                    recommendation="",
                )
            )

        if not wlan.bss_transition:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': 802.11v (BSS Transition) is disabled",
                    detail=(
                        "802.11v lets APs suggest better APs to clients. Without it, roaming "
                        "decisions are entirely up to the client, which may not be optimal."
                    ),
                    recommendation="Enable BSS Transition Management (802.11v).",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > BSS Transition",
                )
            )

        if not wlan.rrm_enabled:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': 802.11k (Radio Resource Management) is disabled",
                    detail=(
                        "802.11k provides clients with a neighbor report so they know which "
                        "APs to scan during roaming, speeding up the process."
                    ),
                    recommendation="Enable 802.11k (RRM).",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced",
                )
            )

    # ------- 4. Minimum RSSI -------
    any_min_rssi = False
    for ap in aps:
        for rt in ap.radio_table:
            if rt.min_rssi_enabled:
                any_min_rssi = True
                if rt.min_rssi > -70:
                    findings.append(
                        Finding(
                            severity=Severity.INFO,
                            module=MODULE,
                            title=f"{ap.display_name}: Min RSSI set aggressively to {rt.min_rssi} dBm",
                            detail=(
                                "A min RSSI above -70 dBm may disconnect clients too aggressively, "
                                "especially in areas with limited AP coverage."
                            ),
                            recommendation="Consider relaxing to -75 or -80 dBm.",
                        )
                    )

    if not any_min_rssi and len(aps) > 1:
        findings.append(
            Finding(
                severity=Severity.WARNING,
                module=MODULE,
                title="No APs have minimum RSSI enabled",
                detail=(
                    "Without min RSSI, APs won't disconnect weak clients. This leads to "
                    "sticky clients that stay connected to a far AP with terrible signal "
                    "instead of roaming to a closer one."
                ),
                recommendation=(
                    "Enable min RSSI on all APs. Recommended: -75 dBm for dense AP "
                    "deployments, -80 dBm for sparse. This forces clients to roam "
                    "when signal degrades."
                ),
                ui_path="Devices > [AP] > Settings > Radios > Min RSSI",
            )
        )

    # ------- 5. Band steering -------
    for wlan in snapshot.wlan_configs:
        if not wlan.enabled:
            continue

        bs = wlan.band_steering_mode
        if bs in ("force_5g", "force"):
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Band steering set to FORCE 5 GHz",
                    detail=(
                        "Force mode prevents 2.4 GHz-only devices (many IoT devices, some "
                        "older smart TVs) from connecting at all. This is a common cause of "
                        "'why can't my device connect' issues."
                    ),
                    recommendation="Change band steering to 'Prefer 5G' instead of 'Force 5G'.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > Band Steering",
                )
            )
        elif bs in ("off", ""):
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Band steering is off",
                    detail="Without band steering, capable clients may connect on 2.4 GHz unnecessarily.",
                    recommendation="Set band steering to 'Prefer 5G' for optimal performance.",
                    ui_path=f"Settings > WiFi > {wlan.name} > Advanced > Band Steering",
                )
            )
        elif bs in ("prefer_5g", "prefer"):
            findings.append(
                Finding(
                    severity=Severity.GOOD,
                    module=MODULE,
                    title=f"SSID '{wlan.name}': Band steering set correctly to 'Prefer 5G'",
                    detail="Good — 5 GHz-capable clients are steered there while 2.4 GHz devices still work.",
                    recommendation="",
                )
            )

    return findings
