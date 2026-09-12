"""Exercise the archive that HACS installs into the integration directory."""

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_release_package import build_release_package


class ReleasePackagingTests(unittest.TestCase):
    def test_archive_installs_directly_into_component(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "tcl_udp_ac.zip"
            build_release_package(root=root, output=output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertEqual(
                    json.loads(archive.read("manifest.json"))["domain"], "tcl_udp_ac"
                )
                self.assertTrue(
                    {
                        "__init__.py",
                        "translations/en.json",
                        "translations/zh-Hans.json",
                        "brand/icon.png",
                    }
                    <= set(names)
                )
                self.assertFalse(
                    any(name.startswith("custom_components/") for name in names)
                )
                self.assertFalse(
                    any(
                        "__pycache__" in name or name.endswith((".pyc", ".DS_Store"))
                        for name in names
                    )
                )

    def test_mismatched_tag_preserves_previous_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "tcl_udp_ac.zip"
            output.write_bytes(b"previous archive")
            with self.assertRaisesRegex(ValueError, "tag"):
                build_release_package(
                    root=Path(__file__).resolve().parents[1],
                    output=output,
                    tag="v99.0.0",
                )
            self.assertEqual(output.read_bytes(), b"previous archive")

    def test_project_version_matches_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            component = root / "custom_components/tcl_udp_ac"
            component.mkdir(parents=True)
            (component / "manifest.json").write_text('{"version": "1.2.3"}')
            (root / "pyproject.toml").write_text('[project]\nversion = "1.2.4"\n')
            with self.assertRaisesRegex(ValueError, "version"):
                build_release_package(root=root, output=root / "tcl_udp_ac.zip")
