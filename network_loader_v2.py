"""Load clean-label network maps even in an already-running Streamlit process.

The previous loader initializes the Louvain network code. This version ensures
that the shared renderer is refreshed if a hosted process still has the
older community-code labels cached in memory.
"""
from __future__ import annotations

import importlib
import threading

from network_loader_v1 import load_network_modules

_lock = threading.Lock()
_REQUIRED_VIEW_RELEASE = 2


def load_clean_label_network_modules():
    networks, view = load_network_modules()
    with _lock:
        if getattr(view, "NETWORK_COMMUNITY_RELEASE", 0) < _REQUIRED_VIEW_RELEASE:
            importlib.invalidate_caches()
            view = importlib.reload(view)
        if getattr(view, "NETWORK_COMMUNITY_RELEASE", 0) < _REQUIRED_VIEW_RELEASE:
            raise RuntimeError("The updated network renderer is not yet available; retry shortly.")
    return networks, view


_networks, _view = load_clean_label_network_modules()
build_network = _networks.build_network
community_partition = _networks.community_partition
make_network_html = _view.make_network_html
