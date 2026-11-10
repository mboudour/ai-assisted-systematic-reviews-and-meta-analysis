"""Verify new guided code is loaded after a Streamlit Cloud deployment."""
import importlib
import sys
import types
import unittest
from unittest.mock import patch

import guided_loader_v3


class AnonymousLoaderTests(unittest.TestCase):
    def test_new_guided_module_is_not_reloaded(self):
        module = types.ModuleType('guided_workflow')
        module.GUIDED_PROVIDER_RELEASE = 2
        module.GUIDED_ANONYMOUS_RELEASE = 1
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader_v3.importlib, 'reload') as reload:
            self.assertIs(guided_loader_v3.load_guided_workflow(), module)
            reload.assert_not_called()

    def test_old_guided_module_is_reloaded(self):
        module = types.ModuleType('guided_workflow')
        module.GUIDED_PROVIDER_RELEASE = 2
        def refresh(old):
            old.GUIDED_ANONYMOUS_RELEASE = 1
            return old
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader_v3.importlib, 'reload', side_effect=refresh) as reload:
            self.assertIs(guided_loader_v3.load_guided_workflow(), module)
            self.assertIs(guided_loader_v3.load_guided_workflow(), module)
            reload.assert_called_once_with(module)

    def test_missing_guided_update_fails_closed(self):
        module = types.ModuleType('guided_workflow')
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader_v3.importlib, 'reload', return_value=module):
            with self.assertRaisesRegex(RuntimeError, 'update is not yet available'):
                guided_loader_v3.load_guided_workflow()

    def test_client_loader_refreshes_old_client(self):
        name = 'openalex_client_loader_v2'
        old = types.ModuleType('openalex_client')
        fresh = types.ModuleType('openalex_client')
        fresh.OPENALEX_CLIENT_RELEASE = 2
        fresh.OpenAlexError = type('OpenAlexError', (Exception,), {})
        fresh.OpenAlexClient = type('OpenAlexClient', (), {})
        fresh.fetch_works = lambda *args, **kwargs: None
        original_loader = sys.modules.get(name)
        try:
            sys.modules.pop(name, None)
            with patch.dict(sys.modules, {'openalex_client': old}), \
                 patch('importlib.reload', return_value=fresh) as reload:
                loader = importlib.import_module(name)
                self.assertIs(loader.fetch_works, fresh.fetch_works)
                reload.assert_called_once_with(old)
        finally:
            sys.modules.pop(name, None)
            if original_loader is not None:
                sys.modules[name] = original_loader


if __name__ == '__main__':
    unittest.main()
