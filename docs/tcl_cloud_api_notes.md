# TCL+ cloud API notes

These notes summarize the TCL+ app traffic captured in
`/Users/driezy/Downloads/tcl/captures/tcl_login_1781544117.jsonl` and how it maps
to this integration.

## Device discovery and IDs

`GET /v1/tclplus/user/user_devices`

Observed purpose: list devices bound to the logged-in TCL+ account.

Important AC fields:

- `deviceId`: cloud TID used by TCL+ cloud endpoints.
- `category`: `AC` for air conditioners.
- `productKey`: product/model key, useful for later product metadata lookup.
- `masterId`: account/home id used by the app as the sender JID prefix.
- `nickName`, `locationName`, `mac`, `deviceType`: user-facing metadata.
- `protocol`: observed `0` for legacy XMPP-style AC and `1` for newer TSL-style AC.
- `energy`: whether the app marks the device as energy-statistics capable.
- `identifiers`: newer TSL-style status values for protocol 1 devices.

Integration status in `0.3.0`: connected. The config flow calls this endpoint
after TCL+ login, shows AC devices in a selector, stores `deviceId` as
`cloud_tid`, derives legacy JIDs, and keeps manual TID/JID entry as fallback.

Legacy JID derivation observed from `POST /v1/control/convertMqtt/{tid}`:

- sender: `{masterId}@tcl.com/PH-android-zx01-2`
- recipient: `{deviceId}@tcl.com/AC-linux-zx01-1`

No captured endpoint returned the full JIDs directly; they are inferred from the
app's `convertMqtt` payloads.

## Product and status APIs

`POST /v1/thing/product_info`

Observed purpose: product metadata for selected devices. It returned
`controlPanelType: "1"` for the newer `45816970` TSL device and
`controlPanelType: "0"` for the legacy `2743138` XMPP device.

Integration status: partially connected. `user_devices.protocol` and
`productKey` are preserved and the `1112013595N` product is resolved to a TSL
profile so it does not fall back to legacy `convertMqtt` writes.

`POST /v1/thing/status`

Observed purpose: TSL-style status for newer devices. Request body was
`{"deviceId":"45816970"}`. The response carries identifiers such as
`powerSwitch`, `workMode`, `currentTemperature`, `targetTemperature`, `ECO`,
`sleep`, `screen`, `beepSwitch`, and outdoor-unit telemetry.

Integration status: connected for product `1112013595N`. The cloud client uses
this native endpoint and normalizes `data.status`, including core climate state,
exact seven-gear fan state, swing, feature state, and every observed diagnostic
field. The legacy `curStatus` endpoint remains limited to legacy profiles.

`POST /v1/control/convertMqtt/{tid}`

Observed purpose: legacy cloud control using an XML/XMPP-like message. Captured
requests targeted the legacy `2743138` device.

Integration status: connected as the optional legacy cloud-control path. Local
UDP remains the primary command path.

## TSL property control

Static analysis of TCL+ 6.0.4 shows property writes are wrapped as:

```json
{
  "msgId": "android_<random>_<timestamp>",
  "version": "1.0",
  "params": [{"targetTemperature": 25.5}],
  "source": "APP"
}
```

The integration mirrors that shape for the `1112013595N` profile:

- target temperature: `POST /v1/tclplus/property/{deviceId}`;
- mode writes: `POST /v1/control/property/{deviceId}` with header
  `sourceType: 2`, carrying `powerSwitch`, `workMode`, and optionally
  `targetTemperature`;
- power writes: property body with `powerSwitch` and `moduleId: "-100"`.

The same property envelope now covers automatic/seven-gear fan, horizontal and
vertical swing, ECO, sleep, turbo, health, display, beep, temperature beep,
auxiliary heat, anti-mildew, soft wind, self-clean, automatic fresh air, and
fresh-air percentage. Each command carries an expected normalized state and is
confirmed by a later native TSL status read; HTTP success alone is not treated
as device application. Protocol 1 disables UDP listener/discovery/status and
legacy XML control entirely.

Observed diagnostics are exposed as diagnostic sensors or binary sensors:
coil/exhaust temperatures, voltage/current, compressor frequency, indoor and
outdoor fan telemetry, wind/fresh-air percentages, self-clean state, expansion
valve, filter blockage, four-way valve and active PTC state, errors, TSL
versions/query time, and AI control source. Fields without a proven physical
unit remain unitless.

The F-series `errorCode` field is a numeric list, but the healthy live device
returns `[48]`: decimal 48 is ASCII `"0"`, and 48 is absent from the product's
control-panel fault table. The integration therefore normalizes `[48]` to
`none`. Defined fault identifiers are rendered using the same short codes as
the product panel (for example, identifier 52 is `E1` and identifier 3 is
`E3`); unknown identifiers remain numeric so future faults are not discarded.

## Electricity and runtime statistics

`GET /v1/ac/statistics/electricity/summary?timeType=1|2|3`

Observed purpose: AC-specific electricity and runtime reporting.

Observed response shape:

- `timeType=1`: weekly blocks with daily rows.
- `timeType=2`: monthly blocks with daily rows.
- `timeType=3`: yearly blocks with monthly rows.
- `ecoDetails`: period totals and row data for electricity, bill, running
  hours, ECO/non-ECO details, average electricity per hour/day, carbon, and
  energy-saving fields.
- `workModeDetails`: period and row breakdowns by running mode.

Important caveat: period totals and row sums do not always reconcile exactly in
the capture. For example, one monthly block reported a period `electricity`
value that differed from the summed daily `electricity` and `realElectricity`
values. Treat this endpoint as a TCL+ reporting API, not as a live meter.

Integration status in `0.4.0`: connected for current-month report totals when
the device was discovered through TCL+ login and a `productKey` is available.
The integration fetches `timeType=2`, selects the current calendar month when it
is present, and exposes diagnostic sensors for:

- current-month energy in kWh;
- current-month runtime in hours.

These sensors use report-total semantics and are not marked as
`total_increasing` utility meters. The report `period_start` is exposed as the
sensor statistics reset boundary.

`POST /v1/dashboard/energyStatistics/detail`

Observed purpose: dashboard-level energy overview. The captured response was not
clearly tied to a single AC device.

Integration status: not connected.

`GET /v1/tclplus/eneryStatis/devices/consumable-deficiency/count`

Observed purpose: consumable-deficiency device count. Despite the path typo and
`eneryStatis` segment, it is not energy usage.

Integration status: not connected.

## Home Assistant mapping notes

Home Assistant has standard sensor metadata for energy-like values, but not a
vendor-standard TCL TID/JID API. The HA-compliant pattern is to keep vendor
details inside config flow setup, assign a stable unique id, and expose entities
only when their semantics are clear.

Useful HA references:

- Config flow: <https://developers.home-assistant.io/docs/config_entries_config_flow_handler/>
- Sensor entity metadata: <https://developers.home-assistant.io/docs/core/entity/sensor/>
- Energy dashboard device sensors: <https://www.home-assistant.io/docs/energy/individual-devices/>
- Repairs issues: <https://developers.home-assistant.io/docs/core/integration-quality-scale/rules/repair-issues>

## Command availability and confirmation

The TCL transports can accept a command without the AC applying it. The
integration therefore treats command sending and state confirmation as separate
steps:

- API client methods record the expected status projection for supported
  climate/switch commands.
- The coordinator refreshes state for up to 30 seconds after the command.
- If the expected status appears, the command is marked confirmed.
- If it does not appear in time, the integration logs a warning, fires the
  `tcl_udp_ac_command_result` event, and creates a Home Assistant Repairs issue.

This deliberately avoids repeated persistent notifications. Users who want
push/mobile alerts can automate from the event and filter by `outcome:
not_confirmed`.

Current and potential future mapping:

- The current-month report entities are diagnostic and do not pretend to be live
  increasing meters.
- A Home Assistant energy dashboard sensor should only be added if we can
  produce a stable kWh value with appropriate `device_class`, unit, and
  `state_class`, or import historical statistics through the proper recorder
  statistics path.
- Runtime uses HA duration semantics only for the clearly labeled current-month
  report total.
