"""Build a component-root ZIP for HACS and manual installation."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
import zipfile
from pathlib import Path


def build_release_package(*, root: Path, output: Path, tag: str | None = None) -> Path:
    """Validate the release version before writing the installable component."""
    component = root / "custom_components/tcl_udp_ac"
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not isinstance(version, str) or not re.fullmatch(
        r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version
    ):
        message = "The manifest version must be X.Y.Z"
        raise ValueError(message)
    if project["project"]["version"] != version:
        message = "Project and manifest version must match"
        raise ValueError(message)
    if tag is not None and tag != f"v{version}":
        message = f"Release tag {tag!r} does not match v{version}"
        raise ValueError(message)

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(component.rglob("*")):
            relative = path.relative_to(component)
            if (
                not path.is_file()
                or "__pycache__" in relative.parts
                or any(part.startswith(".") for part in relative.parts)
                or path.suffix in {".pyc", ".pyo", ".map"}
            ):
                continue
            archive.write(path, relative.as_posix())
    return output


def main() -> None:
    """Build a ZIP from this repository without importing Home Assistant."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/tcl_udp_ac.zip"))
    parser.add_argument("--tag")
    args = parser.parse_args()
    try:
        build_release_package(
            root=Path(__file__).resolve().parents[1], output=args.output, tag=args.tag
        )
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
