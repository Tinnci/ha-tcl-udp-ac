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

Integration status: not connected yet. `user_devices.protocol` is now preserved
so a later implementation can split legacy and TSL behavior without another
config migration.

`POST /v1/thing/status`

Observed purpose: TSL-style status for newer devices. Request body was
`{"deviceId":"45816970"}`. The response carries identifiers such as
`powerSwitch`, `workMode`, `currentTemperature`, `targetTemperature`, `ECO`,
`sleep`, `screen`, `beepSwitch`, and outdoor-unit telemetry.

Integration status: not connected yet. The existing cloud fallback currently
parses the older `/device/getdevicestatus?tid=...&category=AC` response shape.

`POST /v1/control/convertMqtt/{tid}`

Observed purpose: legacy cloud control using an XML/XMPP-like message. Captured
requests targeted the legacy `2743138` device.

Integration status: connected as the optional legacy cloud-control path. Local
UDP remains the primary command path.

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

Integration status: not connected yet.

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

Potential future mapping:

- A daily/monthly report entity could be diagnostic, but should not pretend to
  be a live increasing meter.
- A Home Assistant energy dashboard sensor should only be added if we can
  produce a stable kWh value with appropriate `device_class`, unit, and
  `state_class`, or import historical statistics through the proper recorder
  statistics path.
- Runtime can use HA duration semantics only if the source value is clearly
  defined as a current-period or cumulative duration.
