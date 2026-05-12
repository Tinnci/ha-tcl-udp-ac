PLEASE IMPLEMENT THIS PLAN:
# Codex Execution Prompt — Legacy TCL AC Protocol Profile / Mode Mapping / Documentation Cleanup Plan
# Codex 执行计划 — TCL 老协议空调 Protocol Profile、模式映射与文档清理

> 目标：基于最新抓包文件重新校正 legacy TCL UDP AC device `2743138` 的模式映射、Home Assistant 行为、状态解析、工具测试和文档事实源。
>
> 本次修复的核心不是简单把 Fan 从 `baseMode=7` 改成 `baseMode=0`，而是把老协议行为重构为：
>
> ```text
> capture evidence
>   → protocol truth registry
>   → device protocol profile
>   → command bundle
>   → transport send
>   → status reconciliation
>   → Home Assistant state
> ```
>
> 新抓包是事实源。旧 Markdown、旧测试、旧工具输出可能包含错误、过时或误导信息。必须先从抓包提取事实，再做代码变更，最后清理和重建文档事实入口。

---

## 0. Project Context / 项目背景

项目路径：

```text
/Users/driezy/ha-tcl-udp-ac
```

Home Assistant custom integration:

```text
custom_components/tcl_udp_ac
```

关键目录：

```text
custom_components/tcl_udp_ac
tests
tools
newly_captured
docs
```

新事实源抓包：

```text
/Users/driezy/ha-tcl-udp-ac/newly_captured/tcl_1778556941.jsonl
/Users/driezy/ha-tcl-udp-ac/newly_captured/tcl_1778557400.jsonl
```

其中：

- `tcl_1778556941.jsonl` 包含关键 legacy Fan / Dry / mode 行为证据。
- `tcl_1778557400.jsonl` 包含更丰富、多样的 App 调整行为，应作为更细节的交叉验证来源。
- 两个文件都必须被解析，不允许只看旧文档、旧测试、旧代码或旧推断。

目标 legacy device：

```text
2743138
```

---

## 1. Core Thesis / 核心判断

当前旧逻辑的根本问题是：

```text
把 legacy HVAC mode 当成简单 baseMode 单字段切换。
```

新的实现方向是：

```text
legacy HVAC mode change 应该是 capture-derived command bundle。
```

App 在切换模式时，常常不是只发：

```json
{"baseMode": 2}
```

而是发类似：

```json
{
  "turnOn": 1,
  "baseMode": 2,
  "setTemp": 82,
  "degreeH": 0,
  "windSpd": 0,
  "optSuper": 0
}
```

因此实现必须引入 bounded protocol profile layer，而不是继续在 API、climate、status parser、tool matrix 里散落 `baseMode` 映射。

---

## 2. Paradigm Shift / 范式转移

旧模型：

```text
HA HVAC mode
  → baseMode number
  → send one generic command
```

新模型：

```text
HA intent
  → device protocol profile
  → capture-proven command bundle
  → transport transaction
  → expected status projection
  → profile-aware status reconciliation
  → HA state
```

关键抽象：

```text
ProtocolProfile
TclCommandBundle
CaptureEvidence
LegacyTemperatureCodec
ProfileAwareStatusParser
CommandStatusReconciler
ProtocolTruthRegistry
```

这不是无边界大重构。允许的重构范围只包括：

- protocol profile selection
- legacy command bundle construction
- legacy temperature encoding
- command-to-status reconciliation
- capture-derived documentation truth registry

不允许重构无关 integration 区域。

---

## 3. Evidence Levels / 证据等级

所有抓包结论必须区分证据等级：

```text
Observed:
  抓包里直接存在的 packet / payload 字段。

Inferred:
  根据时间线和用户操作推断该 packet 对应某个 App action。

Implemented:
  代码生成了与 capture-supported profile 一致的 bundle。

Verified:
  单元测试、replay 测试、status reconciliation 或可选 live check 证明行为闭环。
```

禁止：

```text
Observed packet 直接升级成 Verified device behavior。
Inferred action 直接写成 confirmed protocol truth。
旧 Markdown 结论覆盖新抓包。
```

---

## 4. Capture-Derived Current Rules / 当前抓包支持规则

以下规则是实现目标，但必须在 Phase 1 中由 analyzer 重新验证。

### 4.1 Fan / 送风

Legacy Fan 不是 `baseMode=7`。

当前判断：

```text
Fan appears to use baseMode=0.
```

目标 command bundle：

```json
{
  "turnOn": 1,
  "baseMode": 0,
  "setTemp": 73,
  "degreeH": 0,
  "windSpd": 0,
  "optSuper": 0
}
```

解释：

- `setTemp=73` 对应 23°C fallback。
- `degreeH=0`。
- `windSpd=0`。
- `optSuper=0`。
- `windSpd=0` 的英文语义不要过度解释；测试只断言 capture-derived payload。
- Fan Only 在 HA 中仍默认隐藏。
- 用户启用 Fan Only 选项后，必须使用 `baseMode=0`，不是 `7`。

### 4.2 Dry / 除湿

目标 command bundle：

```json
{
  "turnOn": 1,
  "baseMode": 2,
  "setTemp": 82,
  "degreeH": 0,
  "windSpd": 0,
  "optSuper": 0
}
```

解释：

- `setTemp=82` 对应 28°C fallback。
- 如果 HA 当前有合法 target temperature，可使用当前 target。
- 如果没有合法 target，使用 28°C fallback。
- 暂时继续映射为 HA `DRY` / `MODE_DEHUMI`。
- 不要因为“自感 / 质感”等标签或语音描述含糊，就映射成 Auto。

### 4.3 Cool / 制冷

目标 command bundle：

```json
{
  "turnOn": 1,
  "baseMode": 3,
  "setTemp": "<current target temp encoded>",
  "degreeH": "<current half-degree flag if used>",
  "windSpd": 0
}
```

规则：

- 使用 grouped on/mode payload。
- 使用 `turnOn=1`。
- 使用 `baseMode=3`。
- 使用当前 HA target temperature。
- 包含 `degreeH`。
- `windSpd=0`。
- `optSuper=0` 只有在 capture analyzer 标记为 profile-required 时才加入。

### 4.4 Heat / 制热

目标 command bundle：

```json
{
  "turnOn": 1,
  "baseMode": 4,
  "setTemp": "<current target temp encoded>",
  "degreeH": "<current half-degree flag if used>",
  "windSpd": 0
}
```

规则：

- 保持 `baseMode=4`。
- 走 grouped profile command path。
- 不再通过 generic `async_set_power_mode` 简单设置。
- `optSuper=0` 只有在 capture analyzer 标记为 profile-required 时才加入。

### 4.5 Auto / AI

当前抓包没有证明 legacy `2743138` 支持 `baseMode=8` 的 App mode request。

规则：

```text
Auto / AI must remain hidden by default.
Do not advertise Auto as verified.
Do not treat baseMode=8 as supported for legacy 2743138 unless a later capture proves it.
Unsupported Auto must not send any command.
```

### 4.6 Unsupported / Experimental Modes

规则：

```text
Do not claim baseMode=7 or baseMode=8 are supported legacy modes.
Keep them experimental / unsupported unless a later capture proves otherwise.
Unsupported mode must return an explicit unsupported result or raise a known integration exception.
No silent fallback to generic mode command is allowed.
```

---

## 5. Global Implementation Rules / 全局执行规则

1. 先解析新抓包，再改代码。
2. 不要从旧 Markdown 继承 mode 结论。
3. 不要把旧文档中的 `baseMode=7 Fan` 或 `baseMode=8 Auto` 当事实。
4. 所有 legacy mode command 必须来自 capture-derived command bundle。
5. 不要把 `2743138` 检查散落到 API、climate、parser 各处。
6. 只有 protocol profile resolver 可以知道 `2743138 -> Legacy2743138Profile`。
7. modern / non-legacy device 行为必须保持不变，并有测试保护。
8. status parsing 必须 profile-aware。
9. `baseMode=0 -> Fan` 只适用于 legacy profile 语境，不要无证据全局修改所有设备。
10. 不要把 standalone temperature-only experiment 混入 mode profile。
11. standalone `setTemp` 仍视为独立实验，因为当前仍失败或未闭环。
12. live test 必须默认 dry-run。
13. 只有显式 `--allow-live` 才允许发真实命令。
14. live test 必须保证最后 `turnOn=0` 或输出人工确认提示。
15. 不允许 broad mock 伪造抓包结论。
16. 不允许 silent fallback 到 generic mode path。
17. 所有旧文档错误必须降级、清理、标注或合并。
18. 不要为统一格式把 `optSuper=0` 强加到 Cool/Heat；必须由 capture evidence 决定。

---

## 6. Worktree / Commit Safety

每个 phase 开始前运行：

```bash
cd /Users/driezy/ha-tcl-udp-ac
git status --short --branch
```

每次提交前运行：

```bash
git status --short
git diff --name-only
git diff --cached --name-only
```

禁止：

```bash
git add -A
```

禁止宽泛 staging，例如：

```bash
git add docs README.md *.md
git add custom_components/tcl_udp_ac tests tools docs README.md *.md
```

必须使用明确 pathspec，只提交本任务相关文件。

不要提交：

```text
无关抓包
本地 HA 配置
secrets
token
临时日志
__pycache__
.pytest_cache
.ruff_cache
.DS_Store
无关 Markdown
无关 README 改动
```

---

# Phase 0 — Baseline and Entry Point Inventory

## Round 1: Establish Baseline

Goal: 确认 repo 状态、目标设备、现有测试、现有工具、现有文档和抓包文件。

Run:

```bash
cd /Users/driezy/ha-tcl-udp-ac
git status --short --branch
find . -maxdepth 3 -type f | sort | sed -n '1,240p'
ls -lh newly_captured/tcl_1778556941.jsonl newly_captured/tcl_1778557400.jsonl
```

Create or update:

```text
docs/legacy_tcl_mode_fix_baseline.md
```

Record:

- current branch
- dirty files
- existing tests
- existing tools
- existing docs / markdown files
- capture file sizes
- target device ID `2743138`
- old known wrong assumptions
- current implementation entry points
- modern device tests if present

Verification:

```bash
test -f docs/legacy_tcl_mode_fix_baseline.md
```

---

## Round 2: Locate Current Mode Mapping Implementation

Goal: 找到当前 API、climate entity、status parser、tool matrix 中的模式映射点。

Search:

```bash
grep -R "baseMode\|MODE_FAN\|MODE_DEHUMI\|fan_only\|async_set_power_mode\|HVACMode\|optSuper\|windSpd" -n custom_components tests tools docs *.md 2>/dev/null | sed -n '1,260p'
```

Document in baseline:

- API command builder file
- cloud/status parser file
- climate entity HVAC mode handling file
- options flow / config option controlling Fan Only and Auto visibility
- live test tool file
- unit test files
- docs containing old mode claims
- current places that mention `baseMode=7` or `baseMode=8`

Verification:

```bash
grep -n "mode mapping entry points" docs/legacy_tcl_mode_fix_baseline.md
```

---

## Round 3: Phase 0 Commit

Only commit baseline if changed.

```bash
git status --short
git add docs/legacy_tcl_mode_fix_baseline.md
git commit -m "chore(tcl): baseline legacy mode mapping fix"
```

Skip commit if no relevant change.

---

# Phase 1 — Capture Evidence Extraction

## Round 4: Build Capture Parser for Mode Commands

Goal: 用脚本解析两个新抓包文件，输出 mode command evidence，不靠人工猜测。

Create or update:

```text
tools/analyze_legacy_mode_capture.py
```

Inputs:

```text
newly_captured/tcl_1778556941.jsonl
newly_captured/tcl_1778557400.jsonl
```

Script should:

- parse JSONL safely
- detect outbound app/device command packets
- extract payload keys:
  - `turnOn`
  - `baseMode`
  - `setTemp`
  - `degreeH`
  - `windSpd`
  - `optSuper`
  - any mode-related fields
- group consecutive mode-change bundles
- separate ObservedCommand from InferredModeProfile
- classify evidence level:
  - observed
  - inferred
  - capture-supported
  - unsupported
  - experimental
- print a timeline
- emit machine-readable summary

Output:

```text
docs/capture_analysis/legacy_2743138_mode_capture_summary.json
docs/capture_analysis/legacy_2743138_mode_capture_report.md
```

Suggested summary shape:

```json
{
  "deviceId": "2743138",
  "captureFiles": [],
  "observedCommands": [],
  "inferredProfiles": [],
  "unsupportedCandidates": [],
  "fieldEvidence": {},
  "evidenceLevels": {}
}
```

Verification:

```bash
/usr/local/bin/uv run python tools/analyze_legacy_mode_capture.py \
  newly_captured/tcl_1778556941.jsonl \
  newly_captured/tcl_1778557400.jsonl \
  --device-id 2743138 \
  --out-dir docs/capture_analysis

test -f docs/capture_analysis/legacy_2743138_mode_capture_summary.json
test -f docs/capture_analysis/legacy_2743138_mode_capture_report.md
```

---

## Round 5: Assert Capture Facts

Goal: 把关键结论变成可测试断言。

The analyzer must assert:

1. Fan candidate contains:

```json
{"baseMode": 0}
```

2. No verified / supported Fan command uses:

```json
{"baseMode": 7}
```

3. No verified / supported Auto or AI command uses:

```json
{"baseMode": 8}
```

4. Dry candidate contains:

```json
{"baseMode": 2}
```

5. App-style mode changes often bundle:

```text
setTemp + degreeH + windSpd + optSuper
```

6. Analyzer must not label inferred profiles as live verified.

Add CLI flag:

```bash
--assert-legacy-mode-facts
```

Verification:

```bash
/usr/local/bin/uv run python tools/analyze_legacy_mode_capture.py \
  newly_captured/tcl_1778556941.jsonl \
  newly_captured/tcl_1778557400.jsonl \
  --device-id 2743138 \
  --assert-legacy-mode-facts \
  --out-dir docs/capture_analysis
```

---

## Round 6: Add Analyzer Tests

Create tests:

```text
tests/test_legacy_mode_capture_analysis.py
```

Test:

- parser loads both capture files
- report includes both capture filenames
- fan candidate has `baseMode=0`
- no supported generated or inferred profile uses `baseMode=7`
- no supported generated or inferred profile uses `baseMode=8`
- dry candidate has `baseMode=2`
- analyzer distinguishes observed packet from inferred profile
- analyzer reports unsupported / experimental fields separately

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_mode_capture_analysis.py
/usr/local/bin/uv run python -m compileall -q tools tests
```

---

## Round 7: Phase 1 Commit

```bash
git status --short
git add \
  tools/analyze_legacy_mode_capture.py \
  tests/test_legacy_mode_capture_analysis.py \
  docs/capture_analysis/legacy_2743138_mode_capture_summary.json \
  docs/capture_analysis/legacy_2743138_mode_capture_report.md \
  docs/legacy_tcl_mode_fix_baseline.md
git commit -m "test(tcl): extract legacy mode facts from new captures"
```

---

# Phase 2 — Protocol Profile and Command Bundle Redesign

## Round 8: Add Protocol Profile and Command Bundle Layer

Goal: 用 bounded protocol profile layer 替代 scattered `baseMode` assumptions。

Create:

```text
custom_components/tcl_udp_ac/protocol_profiles.py
custom_components/tcl_udp_ac/command_bundles.py
custom_components/tcl_udp_ac/temperature_codec.py
```

Define:

```text
ProtocolProfile
Legacy2743138Profile
DefaultProtocolProfile or existing-modern-profile adapter
TclCommandBundle
CaptureEvidence
LegacyTemperatureCodec
UnsupportedModeResult or known exception type
```

Rules:

- No scattered `baseMode=7` or `baseMode=8` assumptions.
- Device `2743138` resolves to `Legacy2743138Profile`.
- Modern / non-legacy devices keep existing behavior.
- Every legacy command bundle must carry capture evidence metadata or a documented reason.
- Unsupported Auto returns explicit unsupported result and sends no command.
- Mode profile building belongs in `Legacy2743138Profile.build_mode_command(...)` or a directly owned helper.
- Do not create a separate duplicate abstraction unless it is clearly owned by the profile layer.

Suggested command bundle fields:

```python
@dataclass(frozen=True)
class TclCommandBundle:
    intent: str
    payload: dict[str, Any]
    evidence: CaptureEvidence
    requires_power_on: bool
    expected_status: dict[str, Any]
```

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac
```

---

## Round 9: Test Protocol Profile Resolver and Temperature Codec

Create tests:

```text
tests/test_protocol_profiles.py
tests/test_temperature_codec.py
```

Tests:

- profile resolver selects legacy profile for `2743138`
- modern / non-legacy device still uses existing/default path
- Fan Only command bundle has capture evidence
- unsupported Auto returns unsupported and sends no command
- unsupported mode does not fall back to generic baseMode
- `LegacyTemperatureCodec` encodes 23°C fallback as `setTemp=73`, `degreeH=0`
- `LegacyTemperatureCodec` encodes 28°C fallback as `setTemp=82`, `degreeH=0`
- valid current target temperature is encoded consistently
- invalid/missing target uses mode-specific fallback
- half-degree behavior is preserved or explicitly unsupported

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_protocol_profiles.py tests/test_temperature_codec.py
```

---

## Round 10: Capture Replay Contract Tests

Goal: Ensure implementation is derived from capture, not old docs.

Create:

```text
tests/test_legacy_capture_replay_contract.py
```

Tests should load:

```text
newly_captured/tcl_1778556941.jsonl
newly_captured/tcl_1778557400.jsonl
```

Assert:

- generated Fan profile matches captured Fan candidate shape
- generated Dry profile matches captured Dry candidate shape
- no generated supported profile emits `baseMode=7`
- no generated supported profile emits `baseMode=8`
- generated profile field set is justified by observed capture fields
- `optSuper=0` is included only where capture evidence marks it profile-required
- report lists unsupported/experimental fields separately

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_capture_replay_contract.py
```

---

## Round 11: Phase 2 Commit

```bash
git status --short
git add \
  custom_components/tcl_udp_ac/protocol_profiles.py \
  custom_components/tcl_udp_ac/command_bundles.py \
  custom_components/tcl_udp_ac/temperature_codec.py \
  tests/test_protocol_profiles.py \
  tests/test_temperature_codec.py \
  tests/test_legacy_capture_replay_contract.py
git commit -m "feat(tcl): introduce capture-derived protocol profiles"
```

---

# Phase 3 — Legacy Mode Command Profiles

## Round 12: Implement Legacy Mode Command Bundles

Goal: 实现 legacy Cool / Dry / Fan Only / Heat command bundles。

Implementation should live in:

```text
custom_components/tcl_udp_ac/protocol_profiles.py
```

or a directly owned helper imported by `Legacy2743138Profile`.

Do not create duplicate profile systems.

Profiles:

```text
cool
dry
fan_only
heat
```

### fan_only

```python
{
    "turnOn": 1,
    "baseMode": 0,
    "setTemp": 73,
    "degreeH": 0,
    "windSpd": 0,
    "optSuper": 0,
}
```

### dry

```python
{
    "turnOn": 1,
    "baseMode": 2,
    "setTemp": 82,
    "degreeH": 0,
    "windSpd": 0,
    "optSuper": 0,
}
```

Use current target only if valid.

### cool

```python
{
    "turnOn": 1,
    "baseMode": 3,
    "setTemp": current_target_encoded,
    "degreeH": current_degree_h,
    "windSpd": 0,
}
```

Include `optSuper=0` only if capture analyzer marks it profile-required.

### heat

```python
{
    "turnOn": 1,
    "baseMode": 4,
    "setTemp": current_target_encoded,
    "degreeH": current_degree_h,
    "windSpd": 0,
}
```

Include `optSuper=0` only if capture analyzer marks it profile-required.

Rules:

- Do not include Auto.
- Do not include `baseMode=7`.
- Do not include `baseMode=8`.
- Do not silently fallback to generic `async_set_power_mode`.
- If mode unsupported, return explicit unsupported result or raise known integration exception.

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac
```

---

## Round 13: Unit Test Legacy Mode Command Bundles

Create:

```text
tests/test_legacy_mode_profiles.py
```

Tests:

- Fan profile emits:
  - `baseMode=0`
  - `setTemp=73`
  - `degreeH=0`
  - `windSpd=0`
  - `optSuper=0`
- Dry profile emits:
  - `baseMode=2`
  - `setTemp=82`
  - `degreeH=0`
  - `windSpd=0`
  - `optSuper=0`
- Cool profile emits:
  - `turnOn=1`
  - `baseMode=3`
  - current encoded target
  - `windSpd=0`
- Heat profile emits:
  - `turnOn=1`
  - `baseMode=4`
  - current encoded target
  - `windSpd=0`
- Auto profile is not available by default.
- `baseMode=7` is never emitted by Fan Only.
- `baseMode=8` is never emitted by Auto.
- Unsupported Auto sends zero packets.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_mode_profiles.py
```

---

## Round 14: Phase 3 Commit

```bash
git status --short
git add \
  custom_components/tcl_udp_ac/protocol_profiles.py \
  custom_components/tcl_udp_ac/command_bundles.py \
  custom_components/tcl_udp_ac/temperature_codec.py \
  tests/test_legacy_mode_profiles.py
git commit -m "feat(tcl): add legacy command bundles for captured modes"
```

---

# Phase 4 — API Layer Integration

## Round 15: Add API Method for Protocol Profile Commands

Goal: API 层新增 profile command path，而不是继续 generic power mode path。

Locate API class / client module.

Add project-style method such as:

```python
async_set_mode_profile(...)
```

or:

```python
async_send_command_bundle(...)
```

Rules:

- Accept HVAC mode / intent.
- Resolve protocol profile.
- Build `TclCommandBundle`.
- Send grouped command payload.
- Preserve existing non-legacy behavior.
- Only use `Legacy2743138Profile` through resolver.
- Do not affect modern devices.
- Unsupported mode must not send command.

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac
```

---

## Round 16: Test API Legacy Profile Command Path

Add tests:

```text
tests/test_legacy_mode_api.py
```

Test:

- Fan profile API sends grouped payload with `baseMode=0`.
- Dry profile API sends grouped payload with `baseMode=2`.
- Cool / Heat use current target temp.
- API does not call generic `async_set_power_mode` for legacy HVAC mode changes.
- Unsupported Auto does not emit `baseMode=8`.
- Unsupported legacy experimental mode does not emit `baseMode=7`.
- Unsupported mode sends zero packets.
- Non-legacy device still uses existing path.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_mode_api.py
```

---

## Round 17: Phase 4 Commit

```bash
git status --short
git add \
  custom_components/tcl_udp_ac \
  tests/test_legacy_mode_api.py
git commit -m "feat(tcl): route legacy mode changes through protocol profile API"
```

---

# Phase 5 — Profile-Aware Status Parsing and Reconciliation

## Round 18: Make Status Parser Profile-Aware

Goal: 让 cloud/status parser 正确理解 legacy status，同时不全局破坏其他设备。

Legacy profile mapping:

```text
baseMode=0 -> MODE_FAN
baseMode=2 -> MODE_DEHUMI / DRY
baseMode=3 -> COOL
baseMode=4 -> HEAT
```

Rules:

- Mapping applies through `Legacy2743138Profile.parse_status(...)` or equivalent profile-aware path.
- Do not globally map `baseMode=0` to Fan for every TCL device unless existing tests prove it.
- Do not claim `baseMode=7` is supported Fan for legacy `2743138`.
- Do not claim `baseMode=8` is supported Auto for legacy `2743138`.
- If `baseMode=7/8` appears in legacy status, treat as experimental/unknown unless future capture proves it.

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac
```

---

## Round 19: Test Profile-Aware Status Parser

Add/update tests:

```text
tests/test_legacy_status_parser.py
```

Test:

- legacy profile maps `baseMode=0` to `MODE_FAN`.
- legacy profile maps `baseMode=2` to `MODE_DEHUMI` / dry.
- legacy profile maps `baseMode=3` to cool.
- legacy profile maps `baseMode=4` to heat.
- legacy profile treats `baseMode=7` as unsupported/unknown.
- legacy profile treats `baseMode=8` as unsupported/unknown.
- default / modern profile behavior is unchanged.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_status_parser.py
```

---

## Round 20: Command-to-Status Reconciliation Tests

Goal: Prove sent command bundles and parsed cloud status agree.

Create:

```text
tests/test_command_status_reconciliation.py
```

Tests:

- Fan command bundle expected status parses as HA Fan.
- Dry command bundle expected status parses as HA Dry.
- Cool command bundle expected status parses as HA Cool.
- Heat command bundle expected status parses as HA Heat.
- Unknown `baseMode` does not become a supported HA mode.
- `baseMode=7/8` remain unsupported for legacy profile.
- Command expected status and parser mapping stay consistent.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_command_status_reconciliation.py
```

---

## Round 21: Phase 5 Commit

```bash
git status --short
git add \
  custom_components/tcl_udp_ac \
  tests/test_legacy_status_parser.py \
  tests/test_command_status_reconciliation.py
git commit -m "fix(tcl): reconcile legacy command bundles with status parsing"
```

---

# Phase 6 — Home Assistant Climate Behavior

## Round 22: Route HVAC Mode Changes Through Protocol Profiles

Goal: HA 改 HVAC mode 时，legacy 设备使用 profile API。

Update climate entity:

- For legacy `2743138`, HVAC mode changes call profile API / command bundle sender.
- Do not call generic `async_set_power_mode`.
- Fan Only remains hidden unless option-enabled.
- When Fan Only enabled, use `baseMode=0`.
- Auto / AI remains hidden by default.
- Do not advertise Auto as verified.
- Unsupported service-call mode must not send command.

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac
```

---

## Round 23: Test Climate Mode Behavior

Add/update tests:

```text
tests/test_legacy_climate_modes.py
```

Test:

- HVAC cool routes to profile API.
- HVAC dry routes to profile API.
- HVAC heat routes to profile API.
- Fan Only hidden by default.
- Fan Only option-enabled routes to profile API and emits `baseMode=0`.
- Auto hidden by default.
- Auto does not emit `baseMode=8`.
- Auto service-call path sends zero packets or raises explicit unsupported error.
- Existing non-legacy devices still use existing path.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_climate_modes.py
```

---

## Round 24: Phase 6 Commit

```bash
git status --short
git add \
  custom_components/tcl_udp_ac \
  tests/test_legacy_climate_modes.py
git commit -m "fix(tcl): use protocol profiles for HA HVAC mode changes"
```

---

# Phase 7 — Live / Dry-Run Tool Update

## Round 25: Update Mode Matrix Tool

Goal: live/dry-run tool 使用抓包 profile，而不是旧 mode matrix。

Locate tool:

```bash
grep -R "mode matrix\|allow-live\|fan_only\|baseMode" -n tools tests | sed -n '1,200p'
```

Update:

- Dry-run prints capture-derived command bundles.
- Fan uses `baseMode=0`.
- Dry uses `baseMode=2`.
- Cool / Heat use grouped profile path.
- No `baseMode=7/8` shown as supported.
- Temperature-only experiment remains separate.
- Standalone `setTemp` must be labeled experimental/failing/not part of mode profile.

Add safety:

- Default dry-run.
- `--allow-live` required for real command.
- `--device-id` required or printed.
- Optional `--mode` selection.
- Optional `--confirm-final-off`.
- Before live run, print target device ID and command sequence.
- Before live run, print final cleanup command.
- After live run, final command must turn device off or instruct user to verify `turnOn=0`.
- If live run fails before cleanup, print explicit manual recovery instruction.
- Never hide outgoing payload.

Verification:

```bash
/usr/local/bin/uv run python -m compileall -q tools
```

---

## Round 26: Tool Tests

Add/update tests:

```text
tests/test_legacy_mode_tool.py
```

Test:

- dry-run matrix includes Fan `baseMode=0`.
- dry-run matrix includes Dry `baseMode=2`.
- dry-run matrix does not include supported `baseMode=7/8`.
- standalone temperature experiment is separate.
- `--allow-live` is required for live sending.
- dry-run output cites capture-derived mode profiles.
- dry-run output prints payloads visibly.
- live mode requires explicit operator opt-in.

Verification:

```bash
/usr/local/bin/uv run python -m unittest tests/test_legacy_mode_tool.py
```

---

## Round 27: Phase 7 Commit

```bash
git status --short
git add \
  tools \
  tests/test_legacy_mode_tool.py
git commit -m "test(tcl): update mode matrix tool for captured legacy profiles"
```

---

# Phase 8 — Documentation Truth Registry and Cleanup

## Round 28: Inventory Markdown Documentation

Goal: 找出所有可能包含旧错误 mode 映射的文档。

Run:

```bash
find . -iname '*.md' -type f | sort > docs/legacy_tcl_markdown_inventory.txt
grep -R "baseMode=7\|baseMode 7\|baseMode=8\|baseMode 8\|Fan.*7\|Auto.*8\|送风\|自感\|质感\|AI" -n --include='*.md' . | sed -n '1,260p' > docs/legacy_tcl_doc_suspect_claims.txt
```

Create:

```text
docs/legacy_tcl_documentation_audit.md
```

Classify docs:

- Current / keep
- Needs correction
- Superseded
- Historical evidence only
- Contains misinformation
- Should be merged

Verification:

```bash
test -f docs/legacy_tcl_documentation_audit.md
test -f docs/legacy_tcl_markdown_inventory.txt
test -f docs/legacy_tcl_doc_suspect_claims.txt
```

---

## Round 29: Create Protocol Truth Registry

Create:

```text
docs/protocol_truth/legacy_2743138_mode_profiles.md
```

Classify claims:

- Confirmed by capture
- Capture-supported but needs live validation
- Implemented
- Verified by unit test
- Hypothesis
- Superseded
- Do-not-assume

Include:

- capture source files
- target device ID
- Fan profile
- Dry profile
- Cool profile
- Heat profile
- unsupported Auto / old Fan assumptions
- status parser mapping
- HA behavior
- command-to-status reconciliation
- live test instructions
- standalone temperature-only experiment warning
- how to rerun capture analyzer
- evidence level table

Verification:

```bash
test -f docs/protocol_truth/legacy_2743138_mode_profiles.md
grep -n "baseMode=0" docs/protocol_truth/legacy_2743138_mode_profiles.md
grep -n "baseMode=7" docs/protocol_truth/legacy_2743138_mode_profiles.md
```

---

## Round 30: Update or Mark Superseded Docs

For each markdown doc containing wrong claims:

- Correct it if it is current documentation.
- Add top banner if historical:

```markdown
> Superseded note: Legacy Fan mode for device 2743138 is now capture-supported as `baseMode=0`, not `baseMode=7`. See `docs/protocol_truth/legacy_2743138_mode_profiles.md`.
```

- Remove duplicated active instructions where appropriate.
- Do not erase useful historical evidence.
- Every old markdown file containing old mode claims must either:
  - link to the truth registry;
  - be corrected;
  - or be marked historical/superseded.

Verification:

```bash
grep -R "baseMode=7\|baseMode 7\|baseMode=8\|baseMode 8" -n --include='*.md' . | sed -n '1,260p'
```

Remaining matches must be one of:

- historical quote
- superseded warning
- explicit unsupported statement
- truth registry do-not-assume section

---

## Round 31: Phase 8 Commit

```bash
git status --short
git add \
  docs/legacy_tcl_markdown_inventory.txt \
  docs/legacy_tcl_doc_suspect_claims.txt \
  docs/legacy_tcl_documentation_audit.md \
  docs/protocol_truth/legacy_2743138_mode_profiles.md
# Add only explicitly reviewed old docs that were corrected or marked superseded.
git diff --cached --name-only
git commit -m "docs(tcl): establish legacy protocol truth registry"
```

Do not use wide `git add docs README.md *.md`.

---

# Phase 9 — Full Verification and Final Summary

## Round 32: Unit Test Gate

Run:

```bash
/usr/local/bin/uv run python -m unittest discover -s tests
```

Fix failures before continuing.

---

## Round 33: Compile Gate

Run:

```bash
/usr/local/bin/uv run python -m compileall -q custom_components/tcl_udp_ac tests tools
```

Fix failures before continuing.

---

## Round 34: Capture Analyzer Gate

Run:

```bash
/usr/local/bin/uv run python tools/analyze_legacy_mode_capture.py \
  newly_captured/tcl_1778556941.jsonl \
  newly_captured/tcl_1778557400.jsonl \
  --device-id 2743138 \
  --assert-legacy-mode-facts \
  --out-dir docs/capture_analysis
```

Must pass.

---

## Round 35: Dry-Run Tool Gate

Run the tool in dry-run mode only.

Use actual tool path discovered in Phase 7.

Example:

```bash
/usr/local/bin/uv run python tools/<mode_matrix_tool>.py --device-id 2743138 --dry-run
```

Must show:

- Fan bundle with `baseMode=0`
- Dry bundle with `baseMode=2`
- no supported `baseMode=7/8`
- visible outgoing payloads
- temperature-only experiment separate

Do not run live mode automatically.

---

## Round 36: Diff Hygiene Gate

Run:

```bash
git diff --check
git status --short
git diff --name-only
git diff --cached --name-only
```

Fix whitespace errors. Confirm no unrelated files are staged.

---

## Round 37: Optional Guarded Live Check

Only if explicitly allowed by local operator.

Dry-run first:

```bash
/usr/local/bin/uv run python tools/<mode_matrix_tool>.py --device-id 2743138 --dry-run
```

For live:

```bash
/usr/local/bin/uv run python tools/<mode_matrix_tool>.py --device-id 2743138 --allow-live
```

Live requirements:

- Print command sequence before sending.
- Use captured profiles.
- Final state must be `turnOn=0`.
- If cleanup fails, print manual recovery instruction.
- Do not run live mode automatically.

---

## Round 38: Final Summary

Create:

```text
docs/legacy_tcl_mode_fix_completion_summary.md
```

Include:

- capture files used
- facts extracted
- evidence levels
- code files changed
- tests added
- docs cleaned
- unsupported modes
- modern-device regression status
- how to rerun analyzer
- how to run unit tests
- how to run dry-run matrix
- live test warning
- remaining unknowns

Verification:

```bash
test -f docs/legacy_tcl_mode_fix_completion_summary.md
```

---

## Round 39: Final Commit

Before staging:

```bash
git status --short
git diff --name-only
git diff --cached --name-only
```

Stage only explicit task-related files, for example:

```bash
git add \
  custom_components/tcl_udp_ac/protocol_profiles.py \
  custom_components/tcl_udp_ac/command_bundles.py \
  custom_components/tcl_udp_ac/temperature_codec.py \
  tools/analyze_legacy_mode_capture.py \
  tests/test_legacy_mode_capture_analysis.py \
  tests/test_protocol_profiles.py \
  tests/test_temperature_codec.py \
  tests/test_legacy_capture_replay_contract.py \
  tests/test_legacy_mode_profiles.py \
  tests/test_legacy_mode_api.py \
  tests/test_legacy_status_parser.py \
  tests/test_command_status_reconciliation.py \
  tests/test_legacy_climate_modes.py \
  tests/test_legacy_mode_tool.py \
  docs/capture_analysis/legacy_2743138_mode_capture_summary.json \
  docs/capture_analysis/legacy_2743138_mode_capture_report.md \
  docs/legacy_tcl_mode_fix_baseline.md \
  docs/legacy_tcl_documentation_audit.md \
  docs/legacy_tcl_markdown_inventory.txt \
  docs/legacy_tcl_doc_suspect_claims.txt \
  docs/protocol_truth/legacy_2743138_mode_profiles.md \
  docs/legacy_tcl_mode_fix_completion_summary.md
```

Add any additional touched files only after inspecting `git diff --name-only`.

Then:

```bash
git diff --cached --name-only
git commit -m "fix(tcl): use capture-derived legacy protocol profiles"
```

---

# Final Acceptance Criteria

This plan is complete only if:

1. Both new capture files are parsed.
2. Capture analyzer distinguishes observed commands from inferred profiles.
3. Capture analyzer proves Fan candidate uses `baseMode=0`.
4. Analyzer proves no supported legacy Fan command uses `baseMode=7`.
5. Analyzer proves no supported Auto command uses `baseMode=8`.
6. Protocol profile resolver maps device `2743138` to `Legacy2743138Profile`.
7. Device `2743138` checks are not scattered through climate/API/status parser code.
8. Modern / non-legacy device behavior remains unchanged and tested.
9. `TclCommandBundle` or equivalent exists.
10. `CaptureEvidence` or equivalent exists.
11. Legacy temperature codec exists and is tested.
12. Legacy Fan command bundle emits `baseMode=0`.
13. Legacy Fan command bundle emits `setTemp=73`, `degreeH=0`, `windSpd=0`, `optSuper=0`.
14. Legacy Dry command bundle emits `baseMode=2`, `setTemp=82`, `degreeH=0`, `windSpd=0`, `optSuper=0`.
15. Cool / Heat use grouped profile path.
16. `optSuper=0` is not blindly added to Cool/Heat unless capture evidence requires it.
17. HA HVAC mode changes for legacy `2743138` call profile API, not generic `async_set_power_mode`.
18. Unsupported Auto sends no command or raises explicit unsupported error.
19. Status parser maps legacy `baseMode=0` to `MODE_FAN`.
20. Status parser behavior is profile-aware, not globally changed without evidence.
21. Command-to-status reconciliation tests pass.
22. Fan Only remains hidden by default.
23. Fan Only option-enabled uses `baseMode=0`, not `7`.
24. Auto remains hidden by default.
25. Auto is not advertised as verified.
26. Tool dry-run matrix prints captured app-style bundles.
27. Tool dry-run shows payloads visibly.
28. Temperature-only experiment remains separate.
29. Unit tests pass.
30. Compileall passes.
31. Capture analyzer gate passes.
32. Dry-run tool gate passes.
33. `git diff --check` passes.
34. Old misleading docs are corrected, superseded, or marked historical.
35. Protocol truth registry exists.
36. Completion summary exists.
37. No secrets, local HA config, unrelated captures, caches, or unrelated files are committed.
38. No broad mocks fake captured behavior.
39. No silent fallback to generic mode path remains for legacy mode changes.
40. No unsupported `baseMode=7/8` is emitted by supported legacy profiles.

---

# Non-Goals

1. Do not redesign unrelated integration areas.
2. Do not change modern-device behavior unless tests prove no regression.
3. Do not claim Auto/AI support for legacy `2743138`.
4. Do not map Fan to `baseMode=7`.
5. Do not map Auto to `baseMode=8`.
6. Do not treat standalone temperature-only command as solved.
7. Do not run live tests without explicit `--allow-live`.
8. Do not trust old Markdown over new capture evidence.
9. Do not delete historical docs without review.
10. Do not add broad mocks to fake captured behavior.

---

# Allowed Redesign

A bounded redesign is allowed for:

- protocol profile selection
- command bundle construction
- legacy temperature encoding
- command-to-status reconciliation
- capture-derived documentation truth registry

The redesign is allowed only if:

- it reduces scattered `baseMode` assumptions;
- it is covered by unit tests;
- it preserves existing modern-device behavior;
- it makes capture evidence traceable;
- it does not silently fallback to generic command paths;
- it does not claim unsupported modes as verified.
