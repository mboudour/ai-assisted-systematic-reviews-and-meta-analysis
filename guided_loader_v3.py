"""Load the anonymous-OpenAlex-capable guided renderer in hosted Streamlit."""
from __future__ import annotations

import importlib
import threading

_lock = threading.Lock()
_REQUIRED_RELEASE = 1


def load_guided_workflow():
    """Reload once if a host retained an older guided renderer."""
    import guided_workflow

    if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) != _REQUIRED_RELEASE:
        with _lock:
            if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) != _REQUIRED_RELEASE:
                importlib.invalidate_caches()
                guided_workflow = importlib.reload(guided_workflow)
                if getattr(guided_workflow, 'GUIDED_ANONYMOUS_RELEASE', 0) != _REQUIRED_RELEASE:
                    raise RuntimeError('The guided workflow update is not yet available; retry shortly.')
    return guided_workflow
