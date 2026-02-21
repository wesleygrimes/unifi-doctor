# unifi-doctor Protocol Reference

> Language-agnostic specification of the UniFi controller API surface consumed by
> unifi-doctor, the wire-format data shapes, diagnostic rule set, configuration
> file formats, and CLI interaction contract.

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [API Endpoints](#2-api-endpoints)
3. [Response Envelope](#3-response-envelope)
4. [Wire-Format Schemas — Controller Objects](#4-wire-format-schemas--controller-objects)
5. [Device Management Commands](#5-device-management-commands)
6. [Diagnostic Output Schemas](#6-diagnostic-output-schemas)
7. [Configuration & Topology File Formats](#7-configuration--topology-file-formats)
8. [Analysis Pipeline](#8-analysis-pipeline)
9. [Analysis Rules & Thresholds](#9-analysis-rules--thresholds)
10. [Streaming Device Identification](#10-streaming-device-identification)
11. [Channel Planning Algorithm](#11-channel-planning-algorithm)
12. [CLI Contract](#12-cli-contract)
13. [Error Handling Contract](#13-error-handling-contract)

---

## 1. Authentication

### Endpoint

```
POST /api/auth/login
```

### Request Body

```json
{
  "username": "admin",
  "password": "secret"
}
```

### Behaviour

The controller returns HTTP 200 and sets session cookies on success.
All subsequent requests must include these cookies. There is no explicit
logout — the session ends when the HTTP client is closed.

### TLS

| Setting          | Default   | Notes                                              |
|------------------|-----------|----------------------------------------------------|
| Protocol         | HTTPS     | Base URL is typically `https://<controller-ip>`    |
| Verify certs     | **false** | Self-signed certs are standard on UDM hardware    |
| Follow redirects | true      | Some firmware versions redirect                    |

### Timeouts

| Scope      | Value      |
|------------|------------|
| Connection | 10 seconds |
| Request    | 30 seconds |

### Credential Resolution (highest to lowest precedence)

1. Environment variables: `UNIFI_HOST`, `UNIFI_USER`, `UNIFI_PASS`
2. Config file: `~/.unifi-doctor/config.yaml`
3. Defaults: host `https://192.168.1.1`, user `admin`, password empty, site `default`

---

## 2. API Endpoints

All paths below are relative to the controller base URL.
`{site}` defaults to `"default"` and is user-configurable.

### Read (GET)

| Path                                                             | Purpose                       | Returns array of |
|------------------------------------------------------------------|-------------------------------|------------------|
| `/proxy/network/api/s/{site}/stat/device`                        | All devices (APs, gateways, switches) | [Device](#41-device)        |
| `/proxy/network/api/s/{site}/stat/sta`                           | Connected clients (stations)  | [Client](#42-client)        |
| `/proxy/network/api/s/{site}/stat/rogueap`                       | Detected neighbouring APs     | [Rogue AP](#43-rogue-ap)    |
| `/proxy/network/api/s/{site}/rest/wlanconf`                      | WLAN / SSID configurations    | [WLAN Config](#44-wlan-config) |
| `/proxy/network/api/s/{site}/rest/setting`                       | Site-wide settings            | [Site Setting](#45-site-setting) |
| `/proxy/network/api/s/{site}/stat/health`                        | Health subsystem status       | [Health Subsystem](#46-health-subsystem) |
| `/proxy/network/api/s/{site}/stat/event?_limit=500&_sort=-time`  | Recent events (newest first)  | [Event](#47-event)          |
| `/proxy/network/api/s/{site}/stat/routing`                       | Routing table                 | opaque objects   |
| `/proxy/network/api/s/{site}/stat/spectralanalysis`              | Spectral analysis data        | opaque objects   |

All seven primary endpoints (device through event) are fetched concurrently.

### Write (POST)

| Path                                                  | Purpose                |
|-------------------------------------------------------|------------------------|
| `/api/auth/login`                                     | Authenticate           |
| `/proxy/network/api/s/{site}/cmd/devmgr`              | Device management commands (see [section 5](#5-device-management-commands)) |

---

## 3. Response Envelope

Every UniFi controller response follows this JSON structure:

```json
{
  "meta": { "rc": "ok" },
  "data": [ ... ]
}
```

Only the `data` array is consumed. If `data` is absent, treat as empty array.
The `meta` object is not used.

---

## 4. Wire-Format Schemas — Controller Objects

These are the JSON shapes returned by the controller API. Field names
match the wire keys exactly unless an alias is noted. Implementations
should tolerate and preserve unknown fields — the controller may add
new keys in future firmware.

### 4.1 Device

Returned by `/stat/device`. Represents an AP, switch, gateway, or UDM.

| JSON key                 | Type             | Typical default | Notes                                |
|--------------------------|------------------|-----------------|--------------------------------------|
| `mac`                    | string           | `""`            | Colon-separated lowercase MAC        |
| `name`                   | string           | `""`            | User-assigned name                   |
| `model`                  | string           | `""`            | Hardware model identifier            |
| `type`                   | string           | `""`            | `"uap"` (AP), `"usw"` (switch), `"ugw"` (gateway), `"udm"` |
| `state`                  | integer          | `1`             | 1 = connected                        |
| `adopted`                | boolean          | `true`          |                                      |
| `version`                | string           | `""`            | Firmware version                     |
| `ip`                     | string           | `""`            |                                      |
| `uptime`                 | integer          | `0`             | Seconds                              |
| `satisfaction`           | integer          | `100`           | 0–100 score                          |
| `radio_table`            | array of objects | `[]`            | See [Radio Entry](#radio-entry)      |
| `radio_table_stats`      | array of objects | `[]`            | See [Radio Stats Entry](#radio-stats-entry) |
| `port_table`             | array of objects | `[]`            | See [Port Entry](#port-entry)        |
| `uplink`                 | object or null   | `null`          | See [Uplink](#uplink)                |
| `mesh_sta_vap_enabled`   | boolean          | `false`         | Mesh station VAP active              |
| `uplink_type`            | string           | `""`            | `"wire"` or `"wireless"`            |

**Useful derivations:**
- A device is an AP when `type == "uap"`
- A device is a gateway when `type` is `"ugw"` or `"udm"`
- Display name: use `name` if non-empty, otherwise `mac`

#### Radio Entry

Nested within `radio_table`.

| JSON key           | Type           | Typical default | Notes                                  |
|--------------------|----------------|-----------------|----------------------------------------|
| `radio`            | string         | `""`            | `"ng"` (2.4 GHz), `"na"` (5 GHz)     |
| `name`             | string         | `""`            | Interface name (e.g. `"ra0"`, `"rai0"`)|
| `channel`          | integer or string | `0`          | Operating channel                      |
| `ht`               | integer        | `20`            | Channel width in MHz (20/40/80/160)    |
| `tx_power`         | integer        | `0`             | Transmit power (dBm)                   |
| `tx_power_mode`    | string         | `"auto"`        | `"auto"`, `"low"`, `"medium"`, `"high"`, `"custom"` |
| `min_rssi_enabled` | boolean        | `false`         |                                        |
| `min_rssi`         | integer        | `0`             | dBm threshold                          |
| `nss`              | integer        | `1`             | Spatial streams                        |
| `cu_total`         | integer        | `0`             | Channel utilisation %                  |
| `cu_self_rx`       | integer        | `0`             | Self-receive utilisation %             |
| `cu_self_tx`       | integer        | `0`             | Self-transmit utilisation %            |
| `satisfaction`     | integer        | `100`           | 0–100 score                            |
| `noise_floor`      | integer        | `-100`          | dBm                                    |

#### Radio Stats Entry

Nested within `radio_table_stats`. Aggregated view of radio state.

| JSON key      | Type           | Typical default |
|---------------|----------------|-----------------|
| `name`        | string         | `""`            |
| `channel`     | integer or string | `0`          |
| `cu_total`    | integer        | `0`             |
| `cu_self_rx`  | integer        | `0`             |
| `cu_self_tx`  | integer        | `0`             |
| `noise_floor` | integer        | `-100`          |
| `satisfaction`| integer        | `100`           |
| `num_sta`     | integer        | `0`             |

**Radio band identification:** channel > 14 implies 5 GHz; channel 1–14 implies 2.4 GHz.
Radio type strings: `"ng"` / `"ra0"` = 2.4 GHz; `"na"` / `"rai0"` / `"ra1"` = 5 GHz.

#### Port Entry

Nested within `port_table`.

| JSON key      | Type    | Typical default |
|---------------|---------|-----------------|
| `port_idx`    | integer | `0`             |
| `name`        | string  | `""`            |
| `speed`       | integer | `0`             |
| `full_duplex` | boolean | `true`          |
| `rx_errors`   | integer | `0`             |
| `tx_errors`   | integer | `0`             |
| `rx_bytes`    | integer | `0`             |
| `tx_bytes`    | integer | `0`             |
| `up`          | boolean | `false`         |

#### Uplink

Nested within `uplink` (may be null).

| JSON key      | Type    | Typical default |
|---------------|---------|-----------------|
| `type`        | string  | `""`            |
| `speed`       | integer | `0`             |
| `full_duplex` | boolean | `true`          |
| `max_speed`   | integer | `0`             |

### 4.2 Client

Returned by `/stat/sta`. A connected wireless or wired station.

| JSON key       | Type    | Typical default | Notes                                       |
|----------------|---------|-----------------|---------------------------------------------|
| `mac`          | string  | `""`            |                                             |
| `hostname`     | string  | `""`            | mDNS / DHCP hostname                        |
| `name`         | string  | `""`            | User-assigned alias                         |
| `oui`          | string  | `""`            | Vendor OUI string                           |
| `ip`           | string  | `""`            |                                             |
| `ap_mac`       | string  | `""`            | MAC of associated AP                        |
| `essid`        | string  | `""`            | Connected SSID                              |
| `bssid`        | string  | `""`            |                                             |
| `channel`      | integer | `0`             |                                             |
| `radio`        | string  | `""`            |                                             |
| `radio_proto`  | string  | `""`            | `"ac"`, `"ax"`, `"n"`, `"b"`, `"g"`, `"a"` |
| `rssi`         | integer | `0`             | dBm (preferred signal field)                |
| `signal`       | integer | `0`             | dBm (fallback for rssi)                     |
| `noise`        | integer | `0`             | dBm                                         |
| `tx_rate`      | integer | `0`             | PHY rate — may be Mbps or Kbps (see note)   |
| `rx_rate`      | integer | `0`             | PHY rate — may be Mbps or Kbps (see note)   |
| `tx_bytes`     | integer | `0`             |                                             |
| `rx_bytes`     | integer | `0`             |                                             |
| `satisfaction` | integer | `100`           | 0–100                                       |
| `is_wired`     | boolean | `false`         |                                             |
| `is_guest`     | boolean | `false`         |                                             |
| `roam_count`   | integer | `0`             |                                             |
| `uptime`       | integer | `0`             | Seconds                                     |
| `last_seen`    | integer | `0`             | Unix timestamp                              |

**Useful derivations:**
- Display name: prefer `name`, fall back to `hostname`, then `mac`
- Band: channel > 14 = 5 GHz; channel 1–14 = 2.4 GHz

**PHY rate normalisation:**
Some firmware reports rates in Kbps instead of Mbps. If a rate value
exceeds 10,000, divide by 1,000 to get Mbps.

### 4.3 Rogue AP

Returned by `/stat/rogueap`. A neighbouring AP not part of this network.

| JSON key      | Type    | Typical default | Notes                           |
|---------------|---------|-----------------|----------------------------------|
| `mac`         | string  | `""`            |                                  |
| `essid`       | string  | `""`            | Broadcast SSID                   |
| `channel`     | integer | `0`             |                                  |
| `rssi`        | integer | `0`             | As seen by our AP                |
| `age`         | integer | `0`             | Seconds since detection          |
| `radio`       | string  | `""`            |                                  |
| `report_time` | integer | `0`             | Unix timestamp                   |
| `ap_mac`      | string  | `""`            | MAC of our AP that detected this |

### 4.4 WLAN Config

Returned by `/rest/wlanconf`.

| JSON key                | Type    | Typical default | Notes                                  |
|-------------------------|---------|-----------------|----------------------------------------|
| `_id`                   | string  | `""`            | Unique identifier (MongoDB-style)      |
| `name`                  | string  | `""`            | SSID name                              |
| `enabled`               | boolean | `true`          |                                        |
| `wpa_mode`              | string  | `""`            | e.g. `"wpa2"`                          |
| `dtim_mode`             | string  | `"default"`     |                                        |
| `dtim_na`               | integer | `1`             | DTIM period for 5 GHz                  |
| `dtim_ng`               | integer | `1`             | DTIM period for 2.4 GHz               |
| `fast_roaming_enabled`  | boolean | `false`         | 802.11r                                |
| `rrm_enabled`           | boolean | `false`         | 802.11k                                |
| `bss_transition`        | boolean | `false`         | 802.11v                                |
| `band_steering_mode`    | string  | `"off"`         | `"off"`, `"prefer_5g"`, `"force_5g"`  |
| `min_rssi_enabled`      | boolean | `false`         |                                        |
| `min_rssi`              | integer | `0`             | dBm                                    |
| `pmf_mode`              | string  | `"disabled"`    | Protected Management Frames            |
| `multicast_enhance`     | boolean | `false`         | Multicast-to-unicast conversion        |
| `igmp_snooping`         | boolean | `false`         |                                        |
| `wlan_band`             | string  | `"both"`        | `"both"`, `"2g"`, `"5g"`              |

### 4.5 Site Setting

Returned by `/rest/setting`. Each object has a `key` that identifies
the settings section; the remaining fields vary by key. Unknown
keys/fields should be preserved.

| JSON key                 | Type    | Typical default | Notes                              |
|--------------------------|---------|-----------------|-------------------------------------|
| `key`                    | string  | `""`            | Section identifier                  |
| `ips_mode`               | string  | `""`            | `"ids"`, `"ips"`, or empty/disabled |
| `dpi_enabled`            | boolean | `false`         |                                     |
| `sqm_enabled`            | boolean | `false`         |                                     |
| `sqm_download_rate`      | integer | `0`             | Kbps                                |
| `sqm_upload_rate`        | integer | `0`             | Kbps                                |
| `dns1`                   | string  | `""`            |                                     |
| `dns2`                   | string  | `""`            |                                     |
| `upnp_enabled`           | boolean | `false`         |                                     |
| `connectivity_type`      | string  | `""`            |                                     |
| `connectivity_host`      | string  | `""`            |                                     |
| `auto_optimize_enabled`  | boolean | `false`         |                                     |

### 4.6 Health Subsystem

Returned by `/stat/health`.

| JSON key           | Type    | Typical default | Notes                                 |
|--------------------|---------|-----------------|---------------------------------------|
| `subsystem`        | string  | `""`            | e.g. `"wan"`, `"wlan"`, `"www"`       |
| `status`           | string  | `""`            |                                       |
| `num_ap`           | integer | `0`             |                                       |
| `num_sta`          | integer | `0`             | Station count                         |
| `num_adopted`      | integer | `0`             |                                       |
| `num_pending`      | integer | `0`             |                                       |
| `wan_ip`           | string  | `""`            |                                       |
| `tx_bytes_r`       | integer | `0`             | TX throughput (bytes/sec)             |
| `rx_bytes_r`       | integer | `0`             | RX throughput (bytes/sec)             |
| `latency`          | integer | `0`             | ms                                    |
| `uptime`           | integer | `0`             | Seconds                               |
| `drops`            | integer | `0`             |                                       |
| `xput_down`        | float   | `0.0`           | Download throughput (Mbps)            |
| `xput_up`          | float   | `0.0`           | Upload throughput (Mbps)              |
| `speedtest_lastrun`| integer | `0`             | Unix timestamp                        |

### 4.7 Event

Returned by `/stat/event`.

| JSON key     | Type    | Typical default | Notes                    |
|--------------|---------|-----------------|--------------------------|
| `key`        | string  | `""`            | Event type key           |
| `msg`        | string  | `""`            | Human-readable message   |
| `time`       | integer | `0`             | Unix timestamp           |
| `datetime`   | string  | `""`            | Formatted timestamp      |
| `ap`         | string  | `""`            | Related AP MAC           |
| `ap_name`    | string  | `""`            | Related AP name          |
| `user`       | string  | `""`            | Related client MAC       |
| `ssid`       | string  | `""`            | Related SSID             |
| `channel`    | integer | `0`             |                          |
| `guest`      | string  | `""`            |                          |
| `subsystem`  | string  | `""`            |                          |

---

## 5. Device Management Commands

### Endpoint

```
POST /proxy/network/api/s/{site}/cmd/devmgr
```

### Set Radio Table (apply channel plan)

One request per AP. Changes radio channel and width settings.

```json
{
  "cmd": "set-radiotable",
  "mac": "aa:bb:cc:dd:ee:ff",
  "radio_table": [
    {
      "radio": "ng",
      "channel": 6,
      "ht": 20
    },
    {
      "radio": "na",
      "channel": 44,
      "ht": 40
    }
  ]
}
```

| Field                 | Type    | Description                                      |
|-----------------------|---------|--------------------------------------------------|
| `cmd`                 | string  | `"set-radiotable"`                               |
| `mac`                 | string  | Target AP MAC address                            |
| `radio_table[].radio` | string  | `"ng"` (2.4 GHz) or `"na"` (5 GHz)              |
| `radio_table[].channel` | integer | Target channel number                         |
| `radio_table[].ht`   | integer | Channel width in MHz (20, 40, 80, 160)           |

**Success** is indicated by a non-empty `data` array in the response.
APs typically require 30–60 seconds to apply new radio settings.

---

## 6. Diagnostic Output Schemas

These schemas describe the structured output produced by analysis, not
controller API responses.

### Severity

| Value      | Meaning                                     |
|------------|---------------------------------------------|
| `critical` | Immediate impact — fix first                |
| `warning`  | Degrades performance                        |
| `info`     | Informational / optimisation opportunity    |
| `good`     | Correctly configured (positive affirmation) |

### Band

| Value | Meaning      |
|-------|--------------|
| `2g`  | 2.4 GHz      |
| `5g`  | 5 GHz        |
| `6g`  | 6 GHz        |

### Finding

A single diagnostic observation.

| Field            | Type          | Required | Notes                                             |
|------------------|---------------|----------|----------------------------------------------------|
| `severity`       | Severity      | yes      |                                                    |
| `module`         | string        | yes      | e.g. `"rf-analysis"`, `"streaming-diagnosis"`     |
| `title`          | string        | yes      | Brief summary                                      |
| `detail`         | string        | yes      | Full explanation                                   |
| `recommendation` | string        | yes      | Actionable advice (may be empty for `good`)        |
| `ui_path`        | string        | no       | UniFi UI breadcrumb, e.g. `"Settings > WiFi > …"` |
| `api_change`     | object / null | no       | Machine-readable config change payload             |

### Channel Plan Entry

Recommended RF configuration for one AP on one band.

| Field                 | Type           | Required | Notes                             |
|-----------------------|----------------|----------|-----------------------------------|
| `ap_mac`              | string         | yes      |                                   |
| `ap_name`             | string         | yes      |                                   |
| `band`                | Band           | yes      |                                   |
| `current_channel`     | integer/string | no       | Current operating channel         |
| `recommended_channel` | integer        | no       | Suggested channel                 |
| `current_width`       | integer        | no       | Current width (MHz)               |
| `recommended_width`   | integer        | no       | Suggested width (MHz)             |
| `current_power`       | string         | no       | Current TX power mode             |
| `recommended_power`   | string         | no       | Suggested TX power mode           |
| `reason`              | string         | no       | Human-readable justification      |

### Diagnostic Report

Aggregate output of a full scan.

| Field          | Type                 | Notes                          |
|----------------|----------------------|--------------------------------|
| `generated_at` | ISO 8601 timestamp   |                                |
| `modules_run`  | array of strings     | Module identifiers that ran    |
| `findings`     | array of Finding     |                                |
| `channel_plan` | array of Channel Plan Entry |                           |

---

## 7. Configuration & Topology File Formats

### Config File

**Path:** `~/.unifi-doctor/config.yaml`
**File permissions:** 0600 (directory: 0700)

```yaml
controller:
  host: "https://192.168.1.1"
  username: "admin"
  password: ""
  site: "default"
  verify_ssl: false
```

Environment variables override corresponding fields — see
[Credential Resolution](#credential-resolution-highest-to-lowest-precedence).

### Topology File

**Path:** `~/.unifi-doctor/topology.yaml`

Captures the physical layout of APs to contextualise RF analysis.

```yaml
placements:
  - mac: "aa:bb:cc:dd:ee:ff"
    name: "Living Room AP"
    floor: "ground"           # ground | upper | basement | detached
    location_description: "ceiling mount, living room"
    backhaul: "wired"         # wired | wireless_mesh

links:
  - ap1_mac: "aa:bb:cc:dd:ee:ff"
    ap2_mac: "11:22:33:44:55:66"
    distance_ft: 25.0
    barrier: "wall"           # wall | floor_ceiling | outdoor | open_air
```

---

## 8. Analysis Pipeline

### Data Flow

```
User invokes command
       │
       ▼
Authenticate with controller (POST /api/auth/login)
       │
       ▼
Fetch all data (7 GET endpoints, concurrently)
       │
       ▼
Assembled snapshot containing:
  ├── devices (filtered: APs only, plus gateway identification)
  ├── clients
  ├── rogue APs
  ├── WLAN configs
  ├── site settings
  ├── health subsystems
  └── events
       │
       ▼
Analysis modules (each is a stateless function)
  ├── rf-analysis        → findings + channel plan
  ├── roaming-analysis   → findings
  ├── throughput-analysis → findings
  ├── settings-audit     → findings
  └── streaming-diagnosis → findings
       │
       ▼
Diagnostic report (findings + channel plan)
       │
       ▼
Output (formatted terminal display or JSON)
```

### Module Identifiers

| Module                | Produces              | Primary data consumed                           |
|-----------------------|-----------------------|--------------------------------------------------|
| `rf-analysis`         | findings + channel plan | devices (radio tables), rogue APs, events, topology |
| `roaming-analysis`    | findings              | clients, devices, WLAN configs, events           |
| `throughput-analysis` | findings              | clients, devices (ports, uplinks)                |
| `settings-audit`      | findings              | site settings, WLAN configs, gateway firmware    |
| `streaming-diagnosis` | findings              | clients, devices, WLAN configs, events           |

---

## 9. Analysis Rules & Thresholds

### IDS/IPS & Smart Queues

| Rule                                     | Value    | Unit |
|------------------------------------------|----------|------|
| WAN speed above which IDS/IPS causes issues | 1,000 | Mbps |
| Known UDM Pro IDS throughput ceiling     | 850      | Mbps |
| WAN speed above which SQM can't keep up | 500      | Mbps |

### 2.4 GHz RF

| Rule                        | Value        |
|-----------------------------|--------------|
| Valid (non-overlapping) channels | 1, 6, 11   |
| Recommended channel width   | 20 MHz       |
| Recommended TX power        | low          |

### 5 GHz RF

| Rule                                  | Value                                                                  |
|---------------------------------------|------------------------------------------------------------------------|
| Non-DFS channels (UNII-1 + UNII-3)   | 36, 40, 44, 48, 149, 153, 157, 161, 165                              |
| DFS channels                          | 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144 |
| Recommended width (default)           | 40 MHz                                                                 |
| Recommended width (low density)       | 80 MHz                                                                 |
| Max neighbours to allow 80 MHz        | 3                                                                      |
| Indoor TX power                       | medium                                                                 |
| Outdoor TX power                      | high                                                                   |

### Channel Quality

| Rule                           | Value  | Unit |
|--------------------------------|--------|------|
| Channel utilisation warning    | > 50   | %    |
| Noise floor warning            | > −90  | dBm  |

### Client Signal & Roaming

| Rule                              | Value | Unit  |
|-----------------------------------|-------|-------|
| Sticky client RSSI threshold      | −72   | dBm   |
| Min RSSI recommended (dense)      | −75   | dBm   |
| Min RSSI recommended (sparse)     | −80   | dBm   |
| Poor 5 GHz PHY rate               | < 100 | Mbps  |
| Roaming storm threshold           | > 5   | roams/hour |

### Infrastructure

| Rule                           | Value      |
|--------------------------------|------------|
| Expected wired AP uplink speed | 1,000 Mbps |
| Co-located AP interference     | > −50 dBm  |
| Recommended DTIM period        | 1          |
| Recommended band steering      | prefer 5G  |

### Known Buggy Firmware

| Version pattern | Issue                                  |
|-----------------|----------------------------------------|
| `6.5.28`        | WiFi stability issues                  |
| `6.5.29`        | DNS resolution bugs                    |
| `7.0.14`        | Connectivity drops (early 7.x)        |

### PHY Rate Normalisation

Some firmware reports rates in Kbps. If a rate value exceeds 10,000,
divide by 1,000 to convert to Mbps.

### 5 GHz Channel Overlap Test

Two channels overlap when their frequency spans (determined by channel
width) intersect. Channels are spaced 5 MHz apart; a 40 MHz channel
occupies 8 channel positions, an 80 MHz channel occupies 16.

---

## 10. Streaming Device Identification

Devices are classified as streaming devices using three methods,
checked in order. First match wins.

### Method 1 — OUI Prefix

Match the first 8 characters of the client MAC (uppercase,
colon-separated) against this table:

| OUI Prefix(es) | Vendor |
|-----------------|--------|
| `F0:D2:F1` `74:C2:46` `A0:02:DC` `68:54:FD` `40:B4:CD` `FC:65:DE` `84:D6:D0` `34:D2:70` `B0:FC:0D` `0C:47:C9` `44:65:0D` | Amazon |
| `D0:03:4B` `68:DB:CA` `28:6A:BA` `C8:69:CD` `40:CB:C0` `78:7B:8A` `F0:B3:EC` `AC:CF:5C` `70:56:81` | Apple |
| `D8:31:34` `B0:A7:37` `AC:3A:7A` `DC:3A:5E` `B8:3E:59` `CC:6D:A0` `D4:E2:2F` | Roku |
| `F4:F5:D8` `54:60:09` `6C:AD:F8` `A4:77:33` `48:D6:D5` | Google |
| `8C:79:F5` `78:BD:BC` `F4:7B:09` `F8:04:2E` `AC:5A:14` | Samsung |
| `A8:23:FE` `00:AA:70` `64:99:5D` `BC:F5:AC` | LG |
| `FC:F8:AE` `00:24:8D` `28:3F:69` | Sony |
| `B8:E9:37` `00:0E:58` `5C:AA:FD` `78:28:CA` `48:A6:B8` `54:2A:1B` | Sonos |

### Method 2 — Hostname Keywords

Case-insensitive substring match on `hostname` and `name` fields:

```
fire  firetv  fire-tv  firestick  roku  appletv  apple-tv
chromecast  smarttv  smart-tv  samsung-tv  lg-tv  sony-tv
shield  nvidia-shield  tivo  sonos  playstation  xbox
```

### Method 3 — OUI Field Keywords

Case-insensitive substring match on the `oui` field:

```
amazon  roku  apple  google  samsung  lg  sony  sonos  nvidia  tivo
```

### Per-Device Diagnostic Thresholds

| Check                      | Critical          | Warning          | Good            |
|----------------------------|-------------------|------------------|-----------------|
| Signal strength (RSSI)     | < −72 dBm         | −72 to −65 dBm   | >= −65 dBm      |
| Band                       | On 2.4 GHz        | —                | On 5 GHz        |
| PHY rate (min of TX/RX)    | < 50 Mbps         | 50–100 Mbps      | >= 100 Mbps     |

Additional per-device checks: disconnect/deauth event correlation and
SSID settings audit (multicast enhancement, IGMP snooping, DTIM interval).

---

## 11. Channel Planning Algorithm

Produces one channel plan entry per AP per band (2.4 GHz and 5 GHz).

### 2.4 GHz Recommendations

| Parameter  | Value                               |
|------------|-------------------------------------|
| Channel    | Cycle through 1, 6, 11 across APs  |
| Width      | Always 20 MHz                       |
| TX Power   | low                                 |

### 5 GHz Recommendations

| Parameter  | Value                                          |
|------------|------------------------------------------------|
| Channel    | Non-overlapping assignment (see algorithm)     |
| Width      | 40 MHz; 80 MHz only if <= 3 neighbours         |
| TX Power   | medium (indoor) or high (outdoor/detached)     |

### 5 GHz Channel Selection

1. Scan events for radar detections
2. No radar detected → prefer DFS channels (52–144) for less congestion
3. Radar detected → prefer non-DFS channels only
4. Deprioritise channels with heavy neighbour presence (from rogue AP data)
5. Assign N non-overlapping channels (at 40 MHz width) for N APs
6. Fallback priority: DFS → UNII-3 (149–165) → UNII-1 (36–48)

### Outdoor Detection

APs with `floor` set to `"detached"` in the topology file are treated
as outdoor and receive a `"high"` power recommendation instead of
`"medium"`.

---

## 12. CLI Contract

### Global Flags

Available on all commands unless noted.

| Flag             | Short | Type    | Default | Notes                                  |
|------------------|-------|---------|---------|----------------------------------------|
| `--verify-ssl`   |       | boolean | false   | Verify TLS certificates                |
| `--verbose`      | `-v`  | boolean | false   | Log API requests and errors            |
| `--json`         |       | boolean | false   | JSON output instead of formatted table |

### Commands

#### `setup`

Interactive first-run wizard.

**Prompts:** controller URL, username, password (masked), site name.
On successful connection, launches a topology interview that prompts
for each discovered AP's floor, location description, and backhaul
type, plus distance and barrier type for each AP pair.

#### `scan`

Run diagnostic analysis.

| Flag          | Short | Type   | Default | Description                                                    |
|---------------|-------|--------|---------|----------------------------------------------------------------|
| `--module`    | `-m`  | string | (all)   | Run a single module: `rf`, `roaming`, `throughput`, `settings`, `streaming` |

**Output:** Findings grouped by severity with summary counts. If the RF
module ran, a channel plan comparison table is included.

#### `clients`

List connected clients sorted by signal strength.

**Columns:** Client, IP, AP, Band, Channel, Signal, TX Rate, RX Rate, Protocol, Satisfaction.

Signal colour thresholds: green >= −65 dBm, yellow −65 to −72, red < −72.

#### `aps`

List access points with radio and uplink details.

**Columns:** AP, Model, IP, Clients, 2.4G Channel, 2.4G Utilisation, 5G Channel, 5G Utilisation, Uplink, Satisfaction.

Utilisation colour thresholds: green < 30%, yellow 30–50%, red > 50%.

#### `channels`

Display current vs. recommended channel plan side-by-side.

**Columns:** AP, Band, Current Channel → Recommended, Current Width → Recommended, Current Power → Recommended, Reason.

#### `apply-plan`

Apply the recommended channel plan to APs via the controller API.

| Flag        | Type    | Default | Description                       |
|-------------|---------|---------|-----------------------------------|
| `--dry-run` | boolean | false   | Preview changes without applying  |

Does not support `--json`. Prompts for confirmation before applying
(default: no). Sends one `set-radiotable` POST per AP.

#### `watch`

Live-updating terminal dashboard.

| Flag         | Short | Type    | Default | Description               |
|--------------|-------|---------|---------|---------------------------|
| `--interval` | `-i`  | integer | 5       | Refresh interval (seconds)|

Does not support `--json`. Exit with Ctrl+C.

**Layout:** header (timestamp, counts), AP table, client summary,
network health, and 10 most recent events.

#### `export`

Export raw controller data as JSON.

| Flag       | Short | Type   | Default | Description                     |
|------------|-------|--------|---------|---------------------------------|
| `--format` | `-f`  | string | `json`  | Export format                   |
| `--output` | `-o`  | string | `-`     | File path (`-` = stdout)        |

**Top-level keys:** `devices`, `clients`, `rogue_aps`, `wlan_configs`,
`settings`, `health`, `events`, `routing`.

---

## 13. Error Handling Contract

### Authentication

| Condition          | Behaviour                        |
|--------------------|----------------------------------|
| HTTP error         | Display error, exit (code 1)     |
| Connection refused | Display error with host, exit (code 1) |

### Data Fetching

| Condition        | Behaviour                                                      |
|------------------|-----------------------------------------------------------------|
| HTTP 404         | Treat as empty result (endpoint absent on this firmware)       |
| Any other error  | Treat as empty result; log details in verbose mode             |

One endpoint failing does not prevent the others from returning data.
Analysis modules tolerate empty or missing data gracefully.

### Missing Configuration

If no credentials are found (no env vars, no config file):
display message directing user to run `setup`, exit (code 1).
