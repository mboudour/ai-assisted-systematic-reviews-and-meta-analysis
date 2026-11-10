"""Keep the deployed guided renderer synchronized with the page code."""
import sys
import types
import unittest
from unittest.mock import patch

import guided_loader


class GuidedLoaderTests(unittest.TestCase):
    def test_current_module_is_not_reloaded(self):
        module = types.ModuleType('guided_workflow')
        module.GUIDED_PROVIDER_RELEASE = 1
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader.importlib, 'reload') as reload:
            self.assertIs(guided_loader.load_guided_workflow(), module)
            reload.assert_not_called()

    def test_stale_cached_module_is_reloaded_once(self):
        module = types.ModuleType('guided_workflow')
        def refresh(old):
            old.GUIDED_PROVIDER_RELEASE = 1
            return old
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader.importlib, 'reload', side_effect=refresh) as reload:
            self.assertIs(guided_loader.load_guided_workflow(), module)
            self.assertIs(guided_loader.load_guided_workflow(), module)
            reload.assert_called_once_with(module)

    def test_missing_update_fails_closed(self):
        module = types.ModuleType('guided_workflow')
        with patch.dict(sys.modules, {'guided_workflow': module}), \
             patch.object(guided_loader.importlib, 'reload', return_value=module):
            with self.assertRaisesRegex(RuntimeError, 'update is not yet available'):
                guided_loader.load_guided_workflow()


if __name__ == '__main__':
    unittest.main()
