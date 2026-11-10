"""The updated maps must replace cached network code after a hosted update."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch


class NetworkLoaderTests(unittest.TestCase):
    def test_stale_modules_are_reloaded_once_in_order(self):
        stale_networks = types.ModuleType('day2_networks')
        stale_view = types.ModuleType('day2_network_view')
        fresh_networks = types.ModuleType('day2_networks')
        fresh_view = types.ModuleType('day2_network_view')
        fresh_networks.NETWORK_COMMUNITY_RELEASE = 1
        fresh_view.NETWORK_COMMUNITY_RELEASE = 1
        fresh_networks.build_network = lambda *args, **kwargs: None
        fresh_networks.community_partition = lambda *args, **kwargs: {}
        fresh_view.make_network_html = lambda *args, **kwargs: ''
        old = sys.modules.pop('network_loader_v1', None)
        try:
            with patch.dict(sys.modules, {'day2_networks': stale_networks,
                                          'day2_network_view': stale_view}), \
                 patch('importlib.reload', side_effect=[fresh_networks, fresh_view]) as reload:
                loader = importlib.import_module('network_loader_v1')
                self.assertIs(loader.build_network, fresh_networks.build_network)
                self.assertIs(loader.make_network_html, fresh_view.make_network_html)
                self.assertEqual([call.args[0] for call in reload.call_args_list],
                                 [stale_networks, stale_view])
        finally:
            sys.modules.pop('network_loader_v1', None)
            if old is not None:
                sys.modules['network_loader_v1'] = old

    def test_missing_network_update_fails_closed(self):
        stale_networks = types.ModuleType('day2_networks')
        stale_view = types.ModuleType('day2_network_view')
        old = sys.modules.pop('network_loader_v1', None)
        try:
            with patch.dict(sys.modules, {'day2_networks': stale_networks,
                                          'day2_network_view': stale_view}), \
                 patch('importlib.reload', side_effect=[stale_networks, stale_view]):
                with self.assertRaisesRegex(RuntimeError, 'network renderer is not yet available'):
                    importlib.import_module('network_loader_v1')
        finally:
            sys.modules.pop('network_loader_v1', None)
            if old is not None:
                sys.modules['network_loader_v1'] = old

    def test_guided_loader_refreshes_new_networks_before_guided_renderer(self):
        import guided_loader_v4
        guided = types.ModuleType('guided_workflow')
        loader = types.ModuleType('network_loader_v1')
        trace = []
        loader.load_network_modules = lambda: trace.append('networks')
        def reload(module):
            trace.append('guided')
            module.GUIDED_ANONYMOUS_RELEASE = 2
            return module
        with patch.dict(sys.modules, {'guided_workflow': guided, 'network_loader_v1': loader}), \
             patch.object(guided_loader_v4.importlib, 'reload', side_effect=reload):
            self.assertIs(guided_loader_v4.load_guided_workflow(), guided)
        self.assertEqual(trace, ['networks', 'guided'])


if __name__ == '__main__':
    unittest.main()
