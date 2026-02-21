# unifi-doctor

Opinionated diagnostic and optimization tool for UniFi networks (UDM Pro). Connects to the local controller API, runs analysis modules across RF, roaming, throughput, settings, and streaming, then gives you concrete fixes.

---

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- UniFi Dream Machine (Pro) running local controller API

## Install

```bash
git clone https://github.com/youruser/unifi-doctor
cd unifi-doctor
uv sync
```

## Quick Start

```bash
# First-run: save credentials and map your AP layout
uv run unifi-doctor setup

# Run a full diagnostic scan
uv run unifi-doctor scan

# Live dashboard
uv run unifi-doctor watch
```

---

## Commands

### `setup`

First-run wizard. Saves controller credentials to `~/.unifi-doctor/config.yaml`, connects to discover your APs, then walks you through physical placement so the analysis engine knows floor levels and inter-AP distances.

```
╭─ Setup ────────────────────────────────────────────────────────╮
│ UniFi Doctor — Topology Setup                                  │
│                                                                │
│ I'll ask about where each AP is physically located.            │
│ Backhaul type (wired/mesh) is auto-detected from device data.  │
╰────────────────────────────────────────────────────────────────╯

Controller URL [https://192.168.1.1]:
Username [admin]:
Password (hidden):
Site name [default]:

Config saved to ~/.unifi-doctor/config.yaml

Found 3 access point(s):
┌─────────────────┬───────────────────┬──────────┬─────────────┬───────────────┐
│ AP              │ MAC               │ Model    │ IP          │ Backhaul      │
├─────────────────┼───────────────────┼──────────┼─────────────┼───────────────┤
│ Living Room     │ aa:bb:cc:dd:ee:01 │ U6-Pro   │ 192.168.1.2 │ wired         │
│ Office          │ aa:bb:cc:dd:ee:02 │ U6-Lite  │ 192.168.1.3 │ wired         │
│ Basement        │ aa:bb:cc:dd:ee:03 │ U6-Mesh  │ 192.168.1.4 │ wireless mesh │
└─────────────────┴───────────────────┴──────────┴─────────────┴───────────────┘

Floors: [1] ground  [2] upper  [3] basement  [4] detached
Format: 'floor, location' (e.g. 'ground, hallway ceiling') or just 'ground'

  Living Room — floor, location [ground]: ground, living room ceiling
  Office      — floor, location [ground]: ground, office
  Basement    — floor, location [ground]: basement, mechanical room

Map distances between APs? (helps with power analysis) [y/N]: y

  Living Room ↔ Office
    Distance in feet (approximate) [30]: 35
    Barrier: [1] Wall  [2] Floor/Ceiling  [3] Outdoor  [4] Open Air
    Barrier type: 1

  Living Room ↔ Basement
    Distance in feet (approximate) [30]: 20
    Barrier: [1] Wall  [2] Floor/Ceiling  [3] Outdoor  [4] Open Air
    Barrier type: 2

Topology saved to ~/.unifi-doctor/topology.yaml
```

---

### `scan`

Full diagnostic scan across all analysis modules. Groups findings by severity with actionable recommendations and deep-links to the UniFi UI.

```bash
uv run unifi-doctor scan
uv run unifi-doctor scan --module rf       # single module
uv run unifi-doctor scan --json            # machine-readable output
```

```
╭──────────────────────────────────────────────────────────────────────────╮
│ UniFi Doctor — Diagnostic Report                                          │
│ Generated: 2026-02-21 14:32:07                                            │
│ Modules: rf, roaming, throughput, settings, streaming                     │
╰──────────────────────────────────────────────────────────────────────────╯

  🔴 CRITICAL — 2 issues   — fix these first, they're probably causing your streaming failures
  🟠 WARNING  — 4 issues   — these degrade performance
  🟡 INFO     — 3 issues   — optimizations
  🟢 GOOD     — 6 issues   — configured correctly

════════════════════════════════════════════════════════════
🔴 CRITICAL
════════════════════════════════════════════════════════════

  ■ AP Channel Overlap — Living Room and Bedroom on 2.4 GHz ch 6
    rf
    Both APs share channel 6 on 2.4 GHz, 40 ft apart through a wall.
    Co-channel interference is severe at this separation.
    → Change Bedroom AP to channel 1 or 11.
    📍 Settings > WiFi > Radio Management

  ■ Sticky Client — FireTV-Stick
    roaming
    FireTV-Stick (signal: -79 dBm) has not roamed in 47 min despite
    Office AP being within range at -61 dBm.
    → Enable 802.11v BSS Transition and set Min RSSI to -72 dBm.
    📍 Settings > WiFi > [SSID] > Advanced

════════════════════════════════════════════════════════════
🟠 WARNING
════════════════════════════════════════════════════════════

  ■ IDS/IPS Disabled
    settings
    Intrusion detection is not enabled on this network.
    → Enable Threat Management in Network settings.
    📍 Settings > Security > Threat Management

  ■ 2.4 GHz Legacy Device Dragging Down BSS — Roku-Ultra
    throughput
    Roku-Ultra is connected at 54 Mbps (802.11n) on 2.4 GHz,
    lowering the effective throughput floor for all devices on that radio.
    → Move streaming devices to 5 GHz. Consider disabling 2.4 GHz legacy rates.
    📍 Settings > WiFi > Radio Management

...

════════════════════════════════════════════════════════════
🟢 GOOD
════════════════════════════════════════════════════════════

  ■ 802.11r Fast BSS Transition — enabled
    roaming
    Fast roaming (802.11r) is active on all SSIDs.

  ■ SQM / Smart Queue — enabled on WAN
    settings
    Smart Queue is active. Bufferbloat should be under control.
```

---

### `clients`

Table of all connected clients with AP association, signal quality, PHY rates, and satisfaction score.

```bash
uv run unifi-doctor clients
uv run unifi-doctor clients --json
```

```
                                   Connected Clients
┌──────────────────────┬───────────────┬─────────────┬──────┬─────┬──────────┬──────────┬──────────┬───────┬──────────────┐
│ Client               │ IP            │ AP          │ Band │  Ch │ Signal   │  TX Rate │  RX Rate │ Proto │ Satisfaction │
├──────────────────────┼───────────────┼─────────────┼──────┼─────┼──────────┼──────────┼──────────┼───────┼──────────────┤
│ iPhone-Wes           │ 192.168.1.101 │ Living Room │ 5G   │  36 │ -52 dBm  │ 540 Mbps │ 480 Mbps │ ax    │          97% │
│ MacBook-Pro          │ 192.168.1.102 │ Office      │ 5G   │ 149 │ -58 dBm  │ 720 Mbps │ 650 Mbps │ ax    │          94% │
│ iPad-Mini            │ 192.168.1.103 │ Office      │ 5G   │ 149 │ -63 dBm  │ 360 Mbps │ 300 Mbps │ ax    │          91% │
│ FireTV-Stick         │ 192.168.1.115 │ Living Room │ 5G   │  36 │ -79 dBm  │ 130 Mbps │ 110 Mbps │ ac    │          43% │
│ Roku-Ultra           │ 192.168.1.116 │ Living Room │ 2.4G │   6 │ -68 dBm  │  54 Mbps │  48 Mbps │ n     │          62% │
│ Ring-Doorbell        │ 192.168.1.120 │ Living Room │ 2.4G │   6 │ -71 dBm  │  24 Mbps │  18 Mbps │ n     │          55% │
│ NAS-Server           │ 192.168.1.10  │ wired       │ wired│   - │ -        │        - │        - │ -     │            - │
└──────────────────────┴───────────────┴─────────────┴──────┴─────┴──────────┴──────────┴──────────┴───────┴──────────────┘

Total: 6 wireless, 1 wired
```

---

### `aps`

Per-AP overview: channel assignments, channel utilization, uplink type, and satisfaction.

```bash
uv run unifi-doctor aps
uv run unifi-doctor aps --json
```

```
                                    Access Points
┌─────────────┬──────────┬─────────────┬─────────┬────────┬───────────┬───────┬─────────┬────────────┬──────────────┐
│ AP          │ Model    │ IP          │ Clients │ 2.4G Ch│ 2.4G Util │ 5G Ch │ 5G Util │ Uplink     │ Satisfaction │
├─────────────┼──────────┼─────────────┼─────────┼────────┼───────────┼───────┼─────────┼────────────┼──────────────┤
│ Living Room │ U6-Pro   │ 192.168.1.2 │      14 │ 6      │ 47%       │ 36    │ 28%     │ 1000 Mbps  │          88% │
│ Office      │ U6-Lite  │ 192.168.1.3 │       8 │ 11     │ 22%       │ 149   │ 15%     │ 1000 Mbps  │          96% │
│ Basement    │ U6-Mesh  │ 192.168.1.4 │       3 │ 1      │ 18%       │ 157   │  9%     │ MESH       │          81% │
└─────────────┴──────────┴─────────────┴─────────┴────────┴───────────┴───────┴─────────┴────────────┴──────────────┘
```

---

### `channels`

Shows current channel configuration versus the recommended plan generated by the RF analysis engine.

```bash
uv run unifi-doctor channels
uv run unifi-doctor channels --json
```

```
╭──────────────────────────╮
│ Recommended Channel Plan │
╰──────────────────────────╯
┌─────────────┬──────┬────────────┬──────────────────┬───────────────┬─────────┬───────────────┬─────────┬──────────────────────────────────────┐
│ AP          │ Band │ Current Ch │ → Recommended Ch │ Current Width │ → Width │ Current Power │ → Power │ Reason                               │
├─────────────┼──────┼────────────┼──────────────────┼───────────────┼─────────┼───────────────┼─────────┼──────────────────────────────────────┤
│ Living Room │ 2.4G │ 6          │ 6                │ 20 MHz        │ 20 MHz  │ High          │ Medium  │ co-channel neighbor; reduce power    │
│ Bedroom     │ 2.4G │ 6          │ 11               │ 20 MHz        │ 20 MHz  │ High          │ Medium  │ co-channel conflict; moved to ch 11  │
│ Living Room │ 5G   │ 36         │ 36               │ 80 MHz        │ 80 MHz  │ High          │ High    │ no change needed                     │
│ Office      │ 5G   │ 149        │ 149              │ 80 MHz        │ 80 MHz  │ Auto          │ Auto    │ no change needed                     │
│ Basement    │ 5G   │ 157        │ 157              │ 40 MHz        │ 40 MHz  │ Medium        │ Medium  │ no change needed                     │
└─────────────┴──────┴────────────┴──────────────────┴───────────────┴─────────┴───────────────┴─────────┴──────────────────────────────────────┘
```

---

### `apply-plan`

Pushes recommended channel/power changes back to the controller via API.

```bash
uv run unifi-doctor apply-plan --dry-run   # preview only
uv run unifi-doctor apply-plan             # apply with confirmation prompt
```

```
DRY RUN — Changes to apply:

  Living Room 2.4G: channel → 6, width → 20 MHz
  Bedroom     2.4G: channel → 11, width → 20 MHz

Dry run — no changes applied.
```

---

### `watch`

Live dashboard. Polls the controller every N seconds and updates in place.

```bash
uv run unifi-doctor watch
uv run unifi-doctor watch --interval 10
```

```
╭──────────────────────────────────────────────────────────────────────────────────────────╮
│  UniFi Doctor — Live Dashboard  |  Last refresh: 14:33:22  |  APs: 3  Clients: 18        │
╰──────────────────────────────────────────────────────────────────────────────────────────╯
┌──────────────────────────────────────────────────────────────────┐ ┌───────────────────────────────────┐
│                         Access Points                            │ │          Client Summary            │
│ AP           Clients  2.4G Ch  2.4G Util  5G Ch  5G Util  Sat   │ ├─────────────────────┬─────────────┤
├──────────────┼─────────┼─────────┼──────────┼──────┼─────────┤──┤ │ Metric              │ Value       │
│ Living Room       14       6       47%       36     28%   88%   │ ├─────────────────────┼─────────────┤
│ Office             8      11       22%      149     15%   96%   │ │ Total Wireless      │          18 │
│ Basement           3       1       18%      157      9%   81%   │ │ Total Wired         │           4 │
└──────────────────────────────────────────────────────────────────┘ │ On 5 GHz            │          14 │
                                                                      │ On 2.4 GHz          │           4 │
                                                                      │ Poor Signal (<-72)  │           1 │
                                                                      └─────────────────────┴─────────────┘
                                                                      ┌───────────────────────────────────┐
                                                                      │          Network Health            │
                                                                      │ ● wan: ok                          │
                                                                      │   WAN latency: 12ms                │
                                                                      │ ● wlan: ok                         │
                                                                      │   APs: 3  Clients: 18              │
                                                                      │ ● lan: ok                          │
                                                                      └───────────────────────────────────┘
╭──────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Recent Events                                                                                             │
│ 14:33:18  Client FireTV-Stick disconnected from Living Room                                              │
│ 14:33:01  Client iPhone-Wes roamed from Living Room to Office                                            │
│ 14:32:44  AP Living Room: radio settings applied                                                         │
│ 14:32:11  Client MacBook-Pro connected to Office                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────╯

Refreshing every 5s. Press Ctrl+C to stop.
```

---

### `topology`

Renders an ASCII map of your AP layout using the placement data collected during `setup`. Pass `--live` to overlay current client counts.

```bash
uv run unifi-doctor topology
uv run unifi-doctor topology --live
uv run unifi-doctor topology --json
```

```
╭────────────────────────────── Topology Map ────────────────────────────────────────────────╮
│                                                                                             │
│                                                                                             │
│  @  Living Room[G]                                                                          │
│      \                                                                                      │
│       \  35ft                                                                               │
│        =                                                                                    │
│         \                      @  Office[G]                                                 │
│          \                                                                                  │
│           \                                                                                 │
│            20ft                                                                             │
│             #                                                                               │
│              \                                                                              │
│               @  Basement[B]                                                                │
│                                                                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
╭─────────── Legend ──────────────────────────────────────────────────────────────────────────╮
│  @  Access Point    -  Open Air    =  Wall    #  Floor/Ceiling    .  Outdoor                │
│  Floors:  Ground   Upper   Basement   Detached                                             │
╰─────────────────────────────────────────────────────────────────────────────────────────────╯
```

With `--live`:

```
│  @  Living Room[G] (14)                                                                     │
│      \                                                                                      │
│       \  35ft                                                                               │
│        =                                                                                    │
│         \                      @  Office[G] (8)                                             │
│          \                                                                                  │
│            #                                                                                │
│             \                                                                               │
│              @  Basement[B] (3)                                                             │
```

---

### `export`

Dumps the raw network snapshot to JSON for external analysis.

```bash
uv run unifi-doctor export                   # stdout
uv run unifi-doctor export -o snapshot.json  # file
```

---

## Configuration

Credentials and topology are stored in `~/.unifi-doctor/`:

```
~/.unifi-doctor/
├── config.yaml      # controller URL, username, password, site
└── topology.yaml    # AP placements and inter-AP links
```

Environment variables override the config file:

```bash
UNIFI_HOST=https://192.168.1.1 UNIFI_USER=admin UNIFI_PASS=secret uv run unifi-doctor scan
```

---

## Analysis Modules

| Module | What it checks |
|--------|---------------|
| `rf` | Channel overlap, co-channel interference, channel width, TX power; generates channel plan |
| `roaming` | Sticky clients, roaming storms, 802.11r/v/k, minimum RSSI, band steering |
| `throughput` | PHY rates, legacy device drag, mesh backhaul quality, uplink utilization, band ratios |
| `settings` | IDS/IPS, SQM, DPI, DNS, UPnP, DTIM, firmware currency, PMF |
| `streaming` | Identifies streaming devices by OUI/hostname, checks signal, band, and PHY rate per device |

---

## Development

```bash
uv sync --extra dev          # install dev dependencies
uv run pytest                # run tests
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

The project follows protocol-driven development. `docs/PROTOCOL.md` is the authoritative specification for thresholds, API shapes, and output formats. Read it before changing behavioral code.
