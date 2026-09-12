# Releasing / 发布

The prepared version is **0.11.0**. `manifest.json`, `pyproject.toml`, `uv.lock`,
the README and changelog describe the same release. Version 0.11.0 collects
the observation, quiet-control and publication changes since 0.10.0.

Use `uv sync --locked --group dev`, `uv run pytest`, `uv run ruff check` and
`uv run ruff format --check .`. The native unittest command in `AGENTS.md`
remains supported. CI uses the same locked dependencies instead of installing
Home Assistant 2025.2 merely to run Ruff. The integration uses modern config-entry
runtime data; the supported minimum now matches the verified HA 2026.6.3 host.

Build a local installation archive with:

```sh
uv run python scripts/build_release_package.py --tag v0.11.0
```

`dist/tcl_udp_ac.zip` contains `manifest.json`, Python modules, translations and
the established TCL brand images at its root. HACS uses this exact filename.
Extract it directly into `/config/custom_components/tcl_udp_ac` for manual use.

After reviewing and pushing the release commit, create and push its matching
`vX.Y.Z` tag. **Release** also accepts an existing tag as its `version` input.
The workflow checks out that tag for tests, lint, Hassfest, HACS and packaging.
Its reusable Test, Lint and Validate workflows also serve ordinary CI. GitHub
release notes are generated from Git history. An absent tag cannot be silently
created by the upload step.

手动发布必须选择已经存在的标签。校验、打包与上传使用同一标签；归档测试真实执行
打包器，检查安装目录、品牌和双语翻译，并确认版本错误不会覆盖已有归档。
发布时间戳不是家庭设备确认，发布验证也不会向空调下发控制指令。
