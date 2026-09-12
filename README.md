# TCL Air Conditioner for Home Assistant

[![Version](https://img.shields.io/badge/version-0.11.0-blue)](https://github.com/Tinnci/ha-tcl-udp-ac/releases/latest)
[![Test](https://github.com/Tinnci/ha-tcl-udp-ac/actions/workflows/test.yml/badge.svg)](https://github.com/Tinnci/ha-tcl-udp-ac/actions/workflows/test.yml)
[![Validate](https://github.com/Tinnci/ha-tcl-udp-ac/actions/workflows/validate.yml/badge.svg)](https://github.com/Tinnci/ha-tcl-udp-ac/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/docs/faq/custom_repositories/)

<p align="center">
  <img src="custom_components/tcl_udp_ac/brand/logo.png" alt="TCL" height="96">
</p>

Control supported TCL air conditioners from Home Assistant.

Requires Home Assistant 2026.6.3 or later, the household version used for runtime verification.

The integration selects a local UDP or TCL+ cloud protocol for each device.
Legacy devices use local UDP first. Supported Protocol 1 devices use TCL+ TSL cloud control.

One TCL+ account can add multiple air conditioners. Each air conditioner gets its own Home Assistant device.

> [!IMPORTANT]
> This project is an unofficial custom integration. TCL cloud services and device firmware can change without notice.

## Supported devices

Support depends on the device protocol and product profile.
Account discovery alone does not prove control support.

| Device family | Status path | Control path | Support level |
| --- | --- | --- | --- |
| Legacy TCL AC, protocol `0` or no protocol value | Local UDP with optional TCL+ fallback | Local UDP with optional TCL+ fallback | Supported |
| Product `1112013595N`, protocol `1` | TCL+ TSL cloud | TCL+ TSL cloud | Supported profile |
| Other or unknown products | Not documented | Not documented | Open an issue with diagnostics |

The Protocol 1 profile does not send UDP discovery or legacy XML commands.
It uses the TCL+ thing-status and property-control APIs.

## Features

### Climate control

- Power control
- Cool, dry, and heat modes
- Optional fan-only and Auto/AI modes after device-specific confirmation
- Target temperature from 16 °C to 31 °C
- 0.5 °C temperature steps
- Automatic, low, medium, and high fan speeds for legacy devices
- Automatic and seven-gear fan control for product `1112013595N`
- Vertical and horizontal swing control

### Device features

The integration creates only the entities that the selected product profile describes.

- Eco, display, health, sleep, turbo, auxiliary heat, and beep switches
- Protocol 1 switches for anti-mildew, soft wind, self-clean, and fresh-air control
- Protocol 1 fresh-air percentage control
- Outdoor temperature for supported legacy devices
- Protocol 1 temperatures, electrical values, compressor data, fan data, valve state, filter state, and fault diagnostics
- Current-month TCL+ energy and runtime report totals when TCL provides the required metadata

Unknown diagnostic units stay empty. The integration does not invent a unit.

### Account and device management

- Sign in with a TCL+ password or SMS code
- Discover air conditioners from the TCL+ account
- Add another unconfigured device from a loaded account
- Keep one Home Assistant config entry for each physical air conditioner
- Refresh one account token for all devices on that account
- Start Home Assistant reauthentication only after TCL rejects the credentials

The integration does not store the TCL+ password or SMS code.
Home Assistant stores the access token, refresh token, and account ID in config-entry storage.

### State and command handling

- A shared UDP hub routes identified packets to one device.
- The integration drops conflicting or ambiguous identified packets.
- Local UDP state has priority while it is fresh.
- A one-minute coordinator refresh recovers missed status broadcasts.
- Each accepted command waits for a matching device state.
- An unconfirmed command creates a Home Assistant Repairs issue.
- The `tcl_udp_ac_command_result` event provides the result and transport details.

An HTTP or UDP acceptance does not prove that the device applied a command.
The integration confirms the command only when every required field has a matching
report from an observation begun after that command's dispatch started. Cached or
integration-derived values cannot confirm it. The dispatch start is captured before
awaiting transport, so early feedback remains usable. UDP receipt time is captured
before queuing its callback; cloud requests already in flight before dispatch do
not qualify. A late cloud response cannot overwrite a newer requested snapshot.

指令确认要求每个必要字段都有派发开始后的匹配报告，不能只比较合并后的旧缓存或派生值。
派发等待期间提前到达的反馈仍有效；UDP 接收时间在回调入队前采集，派发前已在途的云端查询
不能充当确认，乱序云端响应也不能回写较新的快照。

Indoor temperature relative to a setpoint does not measure compressor activity.
`hvac_mode` requires reported power and mode. Missing feedback remains unknown.
`hvac_action` reports explicit power-off or powered fan-only operation; heating,
cooling, drying, and thermostat idle remain unknown without conclusive activity
feedback. The climate attribute `hvac_action_is_estimated: false` identifies this
behavior for consumers that also support older releases with temperature-derived
actions. Protocol 1 compressor and electrical diagnostics remain available as
separate sensor entities.

内机温度与设定温度的比较不能测量压缩机运行。缺失电源或模式反馈时保留未知；
制热、制冷、除湿和恒温空闲不再由温差推算。明确报告的关机与通电送风仍可表示，
Protocol 1 的压缩机、电气诊断继续作为独立传感器提供。

Each reported field keeps its source and receipt time in an immutable snapshot.
An unrelated temperature or energy update cannot refresh retained power,
compressor or valve feedback. Climate feedback and diagnostic sensors become
unknown or unavailable after 300 seconds without their own report. Repeated
reports of the same value still count as fresh; missing fan and swing feedback
does not become an assumed auto/off setting.

Climate attributes `hvac_mode_observed_at` and `hvac_action_observed_at` expose the
oldest receipt time required for each value. Diagnostic sensors expose `observed_at`
and `observation_source`. Times are UTC ISO 8601 receipt times, not physical
transition timestamps. An unknown action has no observation time. Nested snapshot
values are immutable; compatibility dictionaries remain detached copies.

每个字段分别保留来源与接收时间，局部更新不能刷新旧电源、压缩机或阀门反馈。
气候反馈和诊断字段超过 300 秒未重新报告即为未知或不可用，相同数值的再次报告仍有效。
气候实体提供模式与活动的最早必要报告时间，诊断实体提供 `observed_at` 与
`observation_source`；这些是 UTC 接收时间，不代表精确物理动作时刻。
嵌套快照不可修改，兼容字典输出为独立副本。

## Home Assistant entities

Distinct states, setpoints, physical attributes, sources and availability changes
publish immediately. Repeated identical feedback is coalesced for up to 120 seconds;
a pending callback publishes the last received snapshot even if the device then
falls silent. Report timestamps remain in HA history. Command confirmation and
context-correlated evidence use the newest internal observations independently.

Protocol versions and query-time diagnostics are disabled by default for new
registrations. Existing entity choices are preserved. Physical measurements,
faults, power feedback and valve readings remain enabled. Numeric fan and
expansion-valve readings support long-term measurement statistics on their raw
scale, without an invented unit.

重复观测最多合并 120 秒，所有实际变化与失效恢复立即发布；指令确认仍读取最新内部
观测。纯协议元数据在新注册时默认禁用，已有启用选择保留。风机与膨胀阀按报告原始数值
保留长期统计，不虚构 RPM 或百分比单位。

| Platform | Purpose |
| --- | --- |
| `climate` | Power, mode, temperature, fan, and swing control |
| `switch` | Product-specific feature control |
| `number` | Product-specific numeric control |
| `sensor` | Temperature, cloud reports, and protocol diagnostics |
| `binary_sensor` | Protocol diagnostic states |

Available entities depend on the product profile and the values that the device reports.

## Installation

### HACS

HACS accepts custom repositories that use a supported repository structure (2).

1. Open HACS.
2. Open the menu in the upper-right corner.
3. Select **Custom repositories**.
4. Add `https://github.com/Tinnci/ha-tcl-udp-ac`.
5. Select **Integration** as the type.
6. Select **Add**.
7. Install **TCL UDP Air Conditioner**.
8. Restart Home Assistant.

### Manual installation

1. Download `tcl_udp_ac.zip` from the [latest release](https://github.com/Tinnci/ha-tcl-udp-ac/releases/latest).
2. Extract its contents directly into `/config/custom_components/tcl_udp_ac`.
3. Confirm that `manifest.json` is directly inside that directory.
4. Restart Home Assistant.

Version 0.11.0 introduces the fixed HACS filename and component-root archive.
Earlier release archives contain an extra `custom_components/tcl_udp_ac` directory.

HACS also installs custom integrations under `custom_components` (3).

## Configuration

1. Open **Settings > Devices & services**.
2. Select **Add integration**.
3. Search for **TCL UDP Air Conditioner**.
4. Select one setup method.

### TCL+ account login

Use a TCL+ password or SMS code.
The integration gets renewable tokens and loads the account device list.

Select one air conditioner from the list.
The integration adds its stable TCL device ID and product metadata.

### Existing TCL+ account

Use this method to add another air conditioner from a loaded account.
The device list shows only air conditioners that do not have a config entry.

This method does not ask for the password again.

### Manual token

Use this method only when account login does not support your region or account.
You must supply the device identifiers and captured token.

A manual token has no automatic refresh path.
Home Assistant requests reauthentication if TCL explicitly rejects it.

## Network requirements

Legacy devices require local UDP access.

- Home Assistant listens on UDP port `10074`.
- Home Assistant sends discovery and commands to UDP port `10075`.
- Home Assistant Container must use host networking.
- A firewall or VLAN must permit the required broadcast traffic.

```yaml
services:
  homeassistant:
    network_mode: host
```

Product `1112013595N` does not use local UDP.
It requires access to the TCL+ cloud service.

## Authentication and security

The login flow uses the TCL public key for the login request.
It keeps the password only during the active setup request.

The integration sends all authorized cloud requests through one token manager.
The token manager refreshes the token before a request when necessary.

An explicit HTTP `401` or `403` response can start one refresh and retry.
A second rejection starts Home Assistant reauthentication.

Network errors, server errors, and rate limits do not start reauthentication.
These failures keep the current session for later recovery.

The integration does not add a separate encryption layer for stored tokens.
Protect the Home Assistant configuration directory and its backups.

## Troubleshooting

### The account list does not show a second air conditioner

Confirm that TCL+ shows the device on the same account.
Start the setup flow with **Existing TCL+ account**.
The list excludes devices that already have a config entry.

### A legacy device has no local state

Confirm that Home Assistant uses host networking.
Permit UDP ports `10074` and `10075` between Home Assistant and the device.

Broadcast packets often do not cross a VLAN or routed subnet.
Use the optional TCL+ fallback when local routing cannot carry these packets.

### A Protocol 1 device is unavailable

Confirm that Home Assistant can reach the TCL+ service.
Do not open UDP ports for this device.

### Home Assistant requests reauthentication

Complete the password or SMS flow.
The integration updates all loaded devices that use the same TCL+ account.

Do not reauthenticate because of one DNS, timeout, server, or rate-limit error.
Check later log entries for recovery.

### A command creates a Repairs issue

Check the device state and transport details in the event data.
Confirm that the selected mode or feature works on the device model.

The command can reach a transport and still fail the final state check.

If neither local UDP nor TCL+ cloud accepts a command, the service call now
fails immediately and Home Assistant creates a separate Repairs issue.

Download diagnostics from the integration or device page before reporting a
problem. The report includes the selected protocol profile, enabled transports,
capabilities, normalized state, and recent command outcomes. It redacts tokens,
account and device identifiers, names, rooms, entity IDs, and context IDs.

## Technical documentation

- [Architecture and invariants](docs/architecture.md)
- [TCL+ cloud API notes](docs/tcl_cloud_api_notes.md)
- [Legacy mode evidence](docs/protocol_truth/legacy_2743138_mode_profiles.md)
- [Brand asset provenance](docs/branding.md)
- [Local verification tools](tools/README.md)
- [Release preparation / 发布准备](docs/releasing.md)

## Development

Use `uv` for the Python environment and test commands.

```bash
uv sync --locked --group dev
uv run pytest
uv run python -m compileall -q custom_components/tcl_udp_ac tests
uv run ruff check
uv run ruff format --check .
git diff --check
```

Do not include account credentials, tokens, Home Assistant secrets, or unsanitized packet captures in an issue.

## Contributing

1. Fork the repository.
2. Create a focused branch.
3. Add tests for changed behavior.
4. Run the required checks.
5. Open a pull request.

Use the [bug report](https://github.com/Tinnci/ha-tcl-udp-ac/issues/new?template=bug.yml) for a defect.
Use the [feature request](https://github.com/Tinnci/ha-tcl-udp-ac/issues/new?template=feature_request.yml) for a new capability.

## Documentation style

This README applies practical rules from ASD-STE100 Simplified Technical English, Issue 9 (1).
It uses active voice, short sentences, simple terms, and one term for each concept.

This use is not an ASD-STE100 compliance certification.
Project-specific technical terms remain necessary.

## References

1. ASD Simplified Technical English Maintenance Group. [ASD-STE100 Simplified Technical English, Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf). 2025.
2. HACS. [Custom Repositories](https://www.hacs.xyz/docs/faq/custom_repositories/). Accessed 2026-08-31.
3. HACS. [Integration repository type](https://www.hacs.xyz/docs/use/repositories/type/integration/). Accessed 2026-08-31.

## License

This project uses the [MIT License](LICENSE).

## Trademark

TCL and the TCL logo are trademarks of their respective owner.
This unofficial integration uses them only to identify supported products.

The brand images match the established TCL assets in Home Assistant Brands.
See the [brand asset provenance](docs/branding.md).
