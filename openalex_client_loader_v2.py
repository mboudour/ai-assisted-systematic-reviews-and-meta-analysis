"""Load the current OpenAlex client after a hosted Streamlit code update.

A new loader module name prevents an already-running Streamlit process from
silently using a cached client that predates anonymous-search support.
"""
import importlib

import openalex_client as _client

if getattr(_client, 'OPENALEX_CLIENT_RELEASE', 0) != 2:
    importlib.invalidate_caches()
    _client = importlib.reload(_client)
    if getattr(_client, 'OPENALEX_CLIENT_RELEASE', 0) != 2:
        raise RuntimeError('The OpenAlex client update is not yet available; retry shortly.')

OpenAlexError = _client.OpenAlexError
OpenAlexClient = _client.OpenAlexClient
fetch_works = _client.fetch_works
