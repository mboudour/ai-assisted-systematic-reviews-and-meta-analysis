"""The clean-label renderer must replace cached pre-update code on Streamlit."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class CleanLabelLoaderTests(unittest.TestCase):
    @staticmethod
    def _network_module():
        networks = types.ModuleType("day2_networks")
        networks.build_network = lambda *args, **kwargs: None
        networks.community_partition = lambda *args, **kwargs: {}
        return networks

    def _load_with(self, view_release, reloaded_release=None):
        old_v2 = sys.modules.pop("network_loader_v2", None)
        try:
            networks = self._network_module()
            view = types.ModuleType("day2_network_view")
            view.NETWORK_COMMUNITY_RELEASE = view_release
            view.make_network_html = lambda *args, **kwargs: "old"
            refreshed = types.ModuleType("day2_network_view")
            refreshed.NETWORK_COMMUNITY_RELEASE = reloaded_release
            refreshed.make_network_html = lambda *args, **kwargs: "new"
            v1 = types.ModuleType("network_loader_v1")
            v1.load_network_modules = lambda: (networks, view)
            with patch.dict(sys.modules, {"network_loader_v1": v1}), \
                 patch("importlib.reload", return_value=refreshed) as reload:
                if reloaded_release is not None and reloaded_release < 2:
                    with self.assertRaisesRegex(RuntimeError, "network renderer is not yet available"):
                        importlib.import_module("network_loader_v2")
                else:
                    loader = importlib.import_module("network_loader_v2")
                    expected = refreshed if view_release < 2 else view
                    self.assertIs(loader.build_network, networks.build_network)
                    self.assertIs(loader.community_partition, networks.community_partition)
                    self.assertIs(loader.make_network_html, expected.make_network_html)
                self.assertEqual(reload.call_count, 1 if view_release < 2 else 0)
        finally:
            sys.modules.pop("network_loader_v2", None)
            if old_v2 is not None:
                sys.modules["network_loader_v2"] = old_v2

    def test_reload_cached_old_view(self):
        self._load_with(1, 2)

    def test_keep_already_current_view(self):
        self._load_with(2, None)

    def test_fail_closed_if_update_is_not_available(self):
        self._load_with(1, 1)


if __name__ == "__main__":
    unittest.main()
