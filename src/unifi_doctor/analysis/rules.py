"""Known-good baselines and rule constants.

These are community-consensus best practices from r/Ubiquiti and UniFi
forums, encoded as concrete thresholds for the analysis engine.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# IDS/IPS thresholds
# ---------------------------------------------------------------------------
IDS_IPS_WAN_THRESHOLD_MBPS = 1000  # At or above this, IDS/IPS degrades throughput
UDM_PRO_IDS_MAX_THROUGHPUT_MBPS = 850  # Known ceiling for UDM Pro IDS engine

# ---------------------------------------------------------------------------
# Smart Queues / SQM
# ---------------------------------------------------------------------------
SQM_WAN_THRESHOLD_MBPS = 500  # Above this, UDM Pro can't handle SQM at line rate

# ---------------------------------------------------------------------------
# RF — 2.4 GHz
# ---------------------------------------------------------------------------
VALID_24G_CHANNELS = {1, 6, 11}
RECOMMENDED_24G_WIDTH = 20  # MHz — only valid option for 2.4 GHz
RECOMMENDED_24G_POWER = "low"  # Low or Medium; High causes asymmetric issues

# ---------------------------------------------------------------------------
# RF — 5 GHz
# ---------------------------------------------------------------------------
NON_DFS_5G_CHANNELS = {36, 40, 44, 48, 149, 153, 157, 161, 165}
DFS_5G_CHANNELS = {52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144}
ALL_5G_CHANNELS = NON_DFS_5G_CHANNELS | DFS_5G_CHANNELS

RECOMMENDED_5G_WIDTH_DEFAULT = 40  # MHz — sweet spot for most homes
RECOMMENDED_5G_WIDTH_LOW_DENSITY = 80  # Only if very few neighbors
MAX_NEIGHBORS_FOR_80MHZ = 3

RECOMMENDED_5G_INDOOR_POWER = "medium"
RECOMMENDED_5G_OUTDOOR_POWER = "high"  # For shed/long-distance AP

# ---------------------------------------------------------------------------
# Channel utilization
# ---------------------------------------------------------------------------
CHANNEL_UTIL_WARNING_PCT = 50
NOISE_FLOOR_WARNING_DBM = -90  # Above this is bad

# ---------------------------------------------------------------------------
# Client signal thresholds
# ---------------------------------------------------------------------------
STICKY_CLIENT_RSSI_THRESHOLD = -72  # dBm — below this, client should roam
MIN_RSSI_RECOMMENDED_TIGHT = -75  # For dense AP deployments
MIN_RSSI_RECOMMENDED_LOOSE = -80  # For sparse deployments
POOR_5G_PHY_RATE_MBPS = 100  # Below this on 5 GHz = problem
ROAM_EVENTS_PER_HOUR_THRESHOLD = 5  # More than this = ping-pong

# ---------------------------------------------------------------------------
# AP uplink
# ---------------------------------------------------------------------------
EXPECTED_UPLINK_SPEED_MBPS = 1000


def normalize_rate_mbps(rate: int) -> int:
    """Normalize a PHY rate value to Mbps. Some firmware reports Kbps (>10000)."""
    if rate > 10000:
        return rate // 1000
    return rate


# ---------------------------------------------------------------------------
# Inter-AP signal (power too high indicator)
# ---------------------------------------------------------------------------
INTER_AP_SIGNAL_TOO_HIGH_DBM = -50  # If two APs 100ft+ apart hear each other louder than this

# ---------------------------------------------------------------------------
# WLAN / SSID settings
# ---------------------------------------------------------------------------
RECOMMENDED_DTIM = 1  # For networks with streaming devices
RECOMMENDED_BAND_STEERING = "prefer_5g"  # Not "force_5g"

# ---------------------------------------------------------------------------
# Streaming device vendor OUIs (first 3 bytes of MAC)
# ---------------------------------------------------------------------------
STREAMING_DEVICE_OUIS: dict[str, str] = {
    # Amazon / Fire TV
    "F0:D2:F1": "Amazon",
    "74:C2:46": "Amazon",
    "A0:02:DC": "Amazon",
    "68:54:FD": "Amazon",
    "40:B4:CD": "Amazon",
    "FC:65:DE": "Amazon",
    "84:D6:D0": "Amazon",
    "34:D2:70": "Amazon",
    "B0:FC:0D": "Amazon",
    "0C:47:C9": "Amazon",
    "44:65:0D": "Amazon",
    # Apple TV
    "D0:03:4B": "Apple",
    "68:DB:CA": "Apple",
    "28:6A:BA": "Apple",
    "C8:69:CD": "Apple",
    "40:CB:C0": "Apple",
    "78:7B:8A": "Apple",
    "F0:B3:EC": "Apple",
    "AC:CF:5C": "Apple",
    "70:56:81": "Apple",
    # Roku
    "D8:31:34": "Roku",
    "B0:A7:37": "Roku",
    "AC:3A:7A": "Roku",
    "DC:3A:5E": "Roku",
    "B8:3E:59": "Roku",
    "CC:6D:A0": "Roku",
    "D4:E2:2F": "Roku",
    # Google Chromecast
    "F4:F5:D8": "Google",
    "54:60:09": "Google",
    "6C:AD:F8": "Google",
    "A4:77:33": "Google",
    "48:D6:D5": "Google",
    # Samsung Smart TV
    "8C:79:F5": "Samsung",
    "78:BD:BC": "Samsung",
    "F4:7B:09": "Samsung",
    "F8:04:2E": "Samsung",
    "AC:5A:14": "Samsung",
    # LG Smart TV
    "A8:23:FE": "LG",
    "00:AA:70": "LG",
    "64:99:5D": "LG",
    "BC:F5:AC": "LG",
    # Sony / PlayStation (often used for streaming)
    "FC:F8:AE": "Sony",
    "00:24:8D": "Sony",
    "28:3F:69": "Sony",
    # Sonos (audio streaming)
    "B8:E9:37": "Sonos",
    "00:0E:58": "Sonos",
    "5C:AA:FD": "Sonos",
    "78:28:CA": "Sonos",
    "48:A6:B8": "Sonos",
    "54:2A:1B": "Sonos",
}

# Keywords in hostnames that suggest streaming devices
STREAMING_HOSTNAME_KEYWORDS = [
    "fire",
    "firetv",
    "fire-tv",
    "firestick",
    "roku",
    "appletv",
    "apple-tv",
    "chromecast",
    "smarttv",
    "smart-tv",
    "samsung-tv",
    "lg-tv",
    "sony-tv",
    "shield",
    "nvidia-shield",
    "tivo",
    "sonos",
    "playstation",
    "xbox",
]

# ---------------------------------------------------------------------------
# Known-buggy firmware versions (add as discovered)
# ---------------------------------------------------------------------------
BUGGY_FIRMWARE_PATTERNS: list[dict[str, str]] = [
    {"pattern": "6.5.28", "note": "Known WiFi stability issues, upgrade recommended"},
    {"pattern": "6.5.29", "note": "DNS resolution bugs reported"},
    {"pattern": "7.0.14", "note": "Early 7.x — many users report connectivity drops"},
]

# ---------------------------------------------------------------------------
# Adjacent channel sets (for interference detection)
# ---------------------------------------------------------------------------


def channels_overlap_5g(ch1: int, ch2: int, width1: int = 40, width2: int = 40) -> bool:
    """Check if two 5 GHz channels overlap given their widths."""

    def channel_range(ch: int, width: int) -> set[int]:
        # 5 GHz channels are spaced 5 MHz apart, center frequencies
        # For 20 MHz: just the channel
        # For 40 MHz: channel and channel+4 (or channel-4)
        # For 80 MHz: 4 channels
        base_channels = sorted(ALL_5G_CHANNELS)
        try:
            idx = base_channels.index(ch)
        except ValueError:
            return {ch}

        n_channels = width // 20
        # Approximate: take n_channels starting from the 20MHz group
        group_start = (idx // n_channels) * n_channels
        return set(base_channels[group_start : group_start + n_channels])

    r1 = channel_range(ch1, width1)
    r2 = channel_range(ch2, width2)
    return bool(r1 & r2)


def is_valid_24g_channel(ch: int) -> bool:
    return ch in VALID_24G_CHANNELS


def get_recommended_24g_channels(num_aps: int) -> list[int]:
    """Return recommended 2.4 GHz channel assignments for N APs."""
    base = [1, 6, 11]
    result = []
    for i in range(num_aps):
        result.append(base[i % 3])
    return result


def get_recommended_5g_channels(
    num_aps: int,
    has_radar_events: bool = False,
    neighbor_channels: set[int] | None = None,
) -> list[int]:
    """Return recommended 5 GHz channel assignments for N APs.

    Prefers DFS channels if no radar events detected.
    Avoids channels with heavy neighbor usage.
    """
    neighbor_channels = neighbor_channels or set()

    # Prefer DFS channels (less congested) if no radar
    preferred = sorted(DFS_5G_CHANNELS) if not has_radar_events else []
    # Then UNII-3 (149-165), then UNII-1 (36-48)
    fallback = [149, 153, 157, 161, 36, 40, 44, 48]

    candidates = preferred + [c for c in fallback if c not in preferred]
    # Deprioritize channels with neighbors
    candidates.sort(key=lambda c: (c in neighbor_channels, c))

    # Pick non-overlapping channels for 40 MHz
    selected: list[int] = []
    used_ranges: set[int] = set()
    for ch in candidates:
        # For 40 MHz, each pair uses two 20 MHz channels
        pair = {ch, ch + 4} if ch % 8 == 0 else {ch - 4, ch}
        if not pair & used_ranges:
            selected.append(ch)
            used_ranges |= pair
            if len(selected) >= num_aps:
                break

    # If we still need more, just pick from remaining
    while len(selected) < num_aps:
        for ch in candidates:
            if ch not in selected:
                selected.append(ch)
                break
        else:
            break

    return selected[:num_aps]
