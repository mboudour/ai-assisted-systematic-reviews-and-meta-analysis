"""Load the current guided workflow and network modules on Streamlit Cloud."""
from __future__ import annotations

import importlib
import threading

_lock = threading.Lock()
_REQUIRED_RELEASE = 2


def load_guided_workflow():
    # Refresh the shared graph modules first so the guided renderer's existing
    # module references point at the new implementations even after a hot sync.
    from network_loader_v1 import load_network_modules
    load_network_modules()
    import guided_workflow

    if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) < _REQUIRED_RELEASE:
        with _lock:
            if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) < _REQUIRED_RELEASE:
                importlib.invalidate_caches()
                guided_workflow = importlib.reload(guided_workflow)
                if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) < _REQUIRED_RELEASE:
                    raise RuntimeError('The guided workflow update is not yet available; retry shortly.')
    return guided_workflow
