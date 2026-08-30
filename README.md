# TCL UDP Air Conditioner Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-0.9.4-blue)](https://github.com/Tinnci/ha-tcl-udp-ac/releases)
[![Maintainer](https://img.shields.io/badge/maintainer-@Tinnci-green)](https://github.com/Tinnci)

A robust Home Assistant integration for TCL Air Conditioners that use the local UDP broadcast protocol. This integration provides local, instant feedback control without relying on the cloud for daily operations.

<p align="center">
  <img src="custom_components/tcl_udp_ac/brand/logo.png" alt="TCL UDP Air Conditioner" height="96">
</p>

## ✨ Features

- **🚀 100% Local Control**: Uses UDP broadcast (Port 10074/10075) for instant response and status updates.
- **🌡️ Climate Control**:
  - **Modes**: Cool, Heat, Dry (Dehumidifier). Fan Only and Auto/AI are available as experimental options after live confirmation on your device.
  - **Fan Speeds**: Auto, Low, Medium, High.
  - **Swing Modes**: Vertical, Horizontal, Both, Off.
  - **Target Temperature**: 16°C - 31°C (adjustable in 0.5°C steps).
- **📟 Advanced Features (Switches)**:
  - **Eco Mode**: Toggle energy-saving mode.
  - **Turbo Mode**: Maximize cooling/heating performance.
  - **Sleep Mode**: Optimize for sleeping comfort.
  - **Health Mode**: Toggle health/ionization functions (if supported).
  - **Aux Heat**: Auxiliary heating control.
  - **Display**: Turn the unit's LED display on/off.
  - **Beep**: Enable/disable command confirmation beeps.
- **🌤️ Sensors**:
  - **Outdoor Temperature**: Real-time outdoor temperature monitoring.
  - **Current Month Energy**: TCL+ cloud report total for the current month, exposed as a diagnostic kWh total when device metadata is available.
  - **Current Month Runtime**: TCL+ cloud report running hours for the current month, exposed as a diagnostic duration total when device metadata is available.
- **☁️ TCL+ Login**: Log in with a TCL+ account to obtain refreshable cloud tokens and select discovered AC devices. The integration fills the cloud TID and legacy JIDs automatically when TCL+ returns device metadata.
- **🏠 Multiple ACs per account**: Add another unconfigured AC from an existing loaded TCL+ account without entering the password again. Each AC remains an independent Home Assistant device while credentials refresh together.

## 📦 Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant.
2. Go to **Integrations** > **Triple dots** (top right) > **Custom repositories**.
3. Add this repository URL: `https://github.com/Tinnci/ha-tcl-udp-ac`.
4. Select category: **Integration**.
5. Click **Add**, then find "TCL UDP Air Conditioner" in the list and install it.
6. Restart Home Assistant.

### Updating with HACS

1. Open **HACS** in Home Assistant.
2. Go to **Integrations** and open **TCL UDP Air Conditioner**.
3. Install the latest released version.
4. Restart Home Assistant when HACS prompts for it.

### Option 2: Manual Installation

1. Download the `custom_components/tcl_udp_ac` folder from this repository.
2. Copy it to your Home Assistant's `config/custom_components/` directory.
3. Restart Home Assistant.

### Removing the Integration

1. Remove the integration from **Settings** > **Devices & Services**.
2. Delete `custom_components/tcl_udp_ac` from your Home Assistant config folder.
3. Restart Home Assistant.

## ⚙️ Configuration

1. Go to **Settings** > **Devices & Services**.
2. Click **+ Add Integration**.
3. Search for **TCL UDP Air Conditioner**.
4. Choose a setup method:
   - **TCL+ account login**: log in with password or SMS, then select a discovered AC device. The integration stores refreshable tokens and fills the cloud TID plus legacy sender/device JIDs from TCL+ account metadata.
   - **Existing TCL+ account**: select an already loaded account, refresh its device inventory, then choose an AC that has not been configured. No password is requested or stored.
   - **Manual token entry**: paste a captured token and provide the cloud TID/JIDs yourself.
5. Legacy devices keep local UDP as their primary control path, with cloud status/control as optional fallback.
6. The TCL+ protocol 1 product `1112013595N` is cloud-only. It uses native TSL status and property control for power, modes, target temperature, automatic/seven-gear fan, swing, feature switches, and fresh-air percentage.
7. Protocol 1 also exposes the observed temperatures, electrical values, compressor/fan telemetry, valve/filter/self-clean state, TSL metadata, error codes, and other read-only fields as diagnostic entities. Unknown units are deliberately left unitless.

### TCL+ Authentication

When you configure the integration with TCL+ login, Home Assistant stores the access and refresh tokens in the config entry and refreshes them before authorized cloud requests. Devices logged in with the same TCL+ account share one refresh operation and receive rotated credentials together, without reloading otherwise unchanged runtimes. Tokens are not shown again in the options flow. If the refresh token expires or TCL+ explicitly rejects it, Home Assistant raises a re-authentication flow so you can log in again. Transient network, server, and rate-limit failures keep the existing session and do not incorrectly request reauthentication.

The integration does not save your TCL+ username, password, SMS code, or password hash. Password login hashes the password for TCL's protocol, wraps the login payload with TCL's public-key encryption, and keeps it only for the active config-flow request. Home Assistant persists the returned access token, refresh token, and account ID in its config-entry storage so automatic renewal can continue. These are bearer credentials protected by access to the Home Assistant configuration directory and backups; the integration does not add a separate at-rest encryption layer.

Manual token entry remains available for captured-token setups, but manual tokens cannot be refreshed automatically.

### Command Confirmation and Notifications

For supported commands, the integration separates transport acceptance from
the later status match. Each command records whether cloud, UDP, both, or no
transport accepted it. Only accepted commands enter the confirmation loop.
Home Assistant then refreshes state for up to 30 seconds and checks whether the
expected status is reported back. A match confirms the observed final state;
the device protocols do not provide a transaction ID that could prove the
command caused that state.

If the status matches, the pending command is cleared. If it does not match in
time, the integration logs a warning, fires a `tcl_udp_ac_command_result` event
with `outcome: not_confirmed`, and creates a device-entry-specific Home
Assistant Repairs issue. The event also includes `transport_outcome`, such as
`accepted_by_udp`, `accepted_by_cloud`, or `accepted_by_both`. It does not create
repeated persistent notifications by default. The `transport_attempts` mapping
retains each cloud and UDP result (`accepted`, `rejected`, `skipped`, or
`failed`); users can build their own automations from these fields if they want
mobile/persistent alerts.

### Cloud Energy and Runtime Statistics

Captured TCL+ traffic includes `/v1/ac/statistics/electricity/summary?timeType=1|2|3`, which returns historical electricity and running-hours report buckets with daily/monthly/yearly detail. The integration exposes the current-month TCL+ report totals as diagnostic sensors when the device was discovered through TCL+ login and a `productKey` is available.

Home Assistant energy dashboards expect sensors with clear energy semantics, units, and state classes, such as kWh device energy sensors. Because the TCL+ summary endpoint is a report API rather than a live monotonic meter, these diagnostic sensors use total report semantics and are not marked as total-increasing utility meters.

See `docs/tcl_cloud_api_notes.md` for the captured API mapping and HA entity notes.

Related captured endpoints:

- `/v1/ac/statistics/electricity/summary`: AC electricity/runtime report summary and history.
- `/v1/dashboard/energyStatistics/detail`: dashboard-level overview, not clearly tied to a single AC device.
- `/v1/tclplus/eneryStatis/devices/consumable-deficiency/count`: consumable-deficiency count, not energy usage.

### Network Requirements

This integration communicates via **UDP Multicast/Broadcast**.
- **Docker Users**: You **MUST** run Home Assistant in `host` networking mode.
  ```yaml
  # docker-compose.yml
  services:
    homeassistant:
      network_mode: host
  ```
- **Firewall/VLANs**: Ensure UDP traffic on ports **10074** (Receive) and **10075** (Send) is allowed between Home Assistant and the AC units.

## 🔧 Troubleshooting

### Runtime Architecture

The integration uses one shared UDP hub with a per-device session, source-aware
state reconciliation, independently tracked command confirmations, and an
ordered protocol-driver registry. See
[`docs/architecture.md`](docs/architecture.md) for the compatibility invariants,
multi-device routing rules, and supported extension path.

### Local Verification Tools

Read-only status checks are safe:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --status
```

Live tests require `--allow-live` and now run final power-off cleanup by
default. See `tools/README.md` before running mutating tests.

Useful guarded experiments:

```bash
/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --dry-run \
  --test mode-matrix

/usr/local/bin/uv run python tools/test_control_api.py \
  --capture-file /Users/driezy/Downloads/tcl/captures/tcl_1778552854.jsonl \
  --dry-run \
  --test temp-experiment
```

Temperature is exposed to Home Assistant in Celsius. The legacy cloud path still
uses `setTemp`/`degreeH` internally, and live testing has shown that a successful
API response does not always mean the device accepted the target temperature.
Mode switching uses grouped `turnOn=1 + baseMode=...` commands because live
testing showed bare mode changes can be acknowledged but ignored.
For legacy device `2743138`, the capture-derived mode profiles and unsupported
mode notes are tracked in
`docs/protocol_truth/legacy_2743138_mode_profiles.md`.

### Device Not Discovered / No Status Updates

If you can control the AC but don't see status updates (temperature changes, etc.), your firewall is likely blocking incoming UDP packets on port 10074.

**Test Network Connectivity:**
Execute this command inside your Home Assistant environment/container to verify packet reception:

```python
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', 10074))
print("Listening on 10074...")
while True:
    data, addr = s.recvfrom(1024)
    print(f"Received from {addr}: {data}")
```

**Linux/Firewall Fixes:**

*For `iptables` (Debian/Ubuntu/Standard Linux):*
```bash
sudo iptables -A INPUT -p udp --dport 10074 -j ACCEPT
sudo iptables -A INPUT -p udp --dport 10075 -j ACCEPT
```

*For `nftables` (Alpine/PostmarketOS/Modern Linux):*
```bash
nft add rule inet filter input udp dport 10074 accept comment "TCL AC Status"
```

## 🤝 Contributing

Contributions are welcome!
1. Fork the repo.
2. Create a feature branch.
3. Submit a Pull Request.

## 📄 License

MIT License. See [LICENSE](LICENSE) for more information.

## Trademark

TCL and the TCL logo are trademarks of their respective owner. They are used
only to identify the products supported by this unofficial community
integration; their use does not imply endorsement or affiliation. The bundled
brand images are the same Home Assistant Brands assets used by the existing
`tcl_home_unofficial` and `tcl_tv_remote` community integrations. See
[branding provenance](docs/branding.md).
