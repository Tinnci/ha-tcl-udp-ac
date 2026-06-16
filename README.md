# TCL UDP Air Conditioner Integration for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/badge/version-0.3.0-blue)](https://github.com/Tinnci/ha-tcl-udp-ac/releases)
[![Maintainer](https://img.shields.io/badge/maintainer-@Tinnci-green)](https://github.com/Tinnci)

A robust Home Assistant integration for TCL Air Conditioners that use the local UDP broadcast protocol. This integration provides local, instant feedback control without relying on the cloud for daily operations.

<p align="center">
  <img src="icon.png" alt="Icon" width="128" height="128">
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
- **☁️ TCL+ Login**: Log in with a TCL+ account to obtain refreshable cloud tokens and select discovered AC devices. The integration fills the cloud TID and legacy JIDs automatically when TCL+ returns device metadata.

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
   - **Manual token entry**: paste a captured token and provide the cloud TID/JIDs yourself.
5. Keep local UDP as the primary control path. Cloud status fallback and legacy cloud control are optional helpers for networks that miss UDP updates.
6. For newer TCL+ protocol 1 devices, captured traffic shows TSL-style APIs such as `/v1/thing/status`. This release discovers those devices and stores their TID/JID defaults, but the newer cloud status/control path is not fully mapped yet.

### Cloud Energy and Runtime Statistics

Captured TCL+ traffic includes `/v1/ac/statistics/electricity/summary?timeType=1|2|3`, which returns historical electricity and running-hours report buckets with daily/monthly/yearly detail. Home Assistant energy dashboards expect sensors with clear energy semantics, units, and state classes, such as kWh device energy sensors. Because the TCL+ summary endpoint is a report API rather than a live monotonic meter, this release does not expose those values as HA energy sensors yet.

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
