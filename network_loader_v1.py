"""Load the Louvain-capable network modules after Streamlit code updates.

A versioned module name prevents a long-running Streamlit process from using
cached network modules from before the equal-size/community-color update.
"""
from __future__ import annotations

import importlib
import threading

_lock = threading.Lock()
_REQUIRED_RELEASE = 1


def load_network_modules():
    import day2_networks
    import day2_network_view

    with _lock:
        importlib.invalidate_caches()
        if getattr(day2_networks, 'NETWORK_COMMUNITY_RELEASE', 0) < _REQUIRED_RELEASE:
            day2_networks = importlib.reload(day2_networks)
        if getattr(day2_network_view, 'NETWORK_COMMUNITY_RELEASE', 0) < _REQUIRED_RELEASE:
            day2_network_view = importlib.reload(day2_network_view)
        if (getattr(day2_networks, 'NETWORK_COMMUNITY_RELEASE', 0) < _REQUIRED_RELEASE or
                getattr(day2_network_view, 'NETWORK_COMMUNITY_RELEASE', 0) < _REQUIRED_RELEASE):
            raise RuntimeError('The updated network renderer is not yet available; retry shortly.')
    return day2_networks, day2_network_view


_networks, _view = load_network_modules()
build_network = _networks.build_network
community_partition = _networks.community_partition
make_network_html = _view.make_network_html
