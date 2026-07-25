"""HTTP session construction.

Kept in its own module so both the manifest layer and the download layer share
one retry/User-Agent policy, and so tests can inject a stub session instead.
"""

from __future__ import annotations

from typing import Any

DEFAULT_RETRIES = 3
DEFAULT_BACKOFF = 1.0
RETRY_STATUS = (429, 500, 502, 503, 504)


def build_session(
    *,
    user_agent: str,
    retries: int = DEFAULT_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF,
) -> Any:
    """Return a :class:`requests.Session` with retries and a User-Agent set.

    Repositories that publish IIIF are often small institutional servers, so a
    descriptive User-Agent (rather than the library default) and a polite
    exponential backoff on 429/5xx are part of behaving well as a client.
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff_factor,
        status_forcelist=RETRY_STATUS,
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": user_agent})
    return session
