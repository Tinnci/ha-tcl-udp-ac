"""Shared integration runtime tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from tests.test_protocol_commands import load_integration_module


class IntegrationRuntimeTest(unittest.TestCase):
    def test_all_entries_share_one_udp_hub(self) -> None:
        runtime_mod = load_integration_module("integration_runtime")
        hass = SimpleNamespace(data={})

        first = runtime_mod.get_integration_runtime(hass)
        second = runtime_mod.get_integration_runtime(hass)

        self.assertIs(first, second)
        self.assertIs(first.udp_hub, second.udp_hub)


if __name__ == "__main__":
    unittest.main()
