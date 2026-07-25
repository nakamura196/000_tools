from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Dict[str, Any]:
    with open(FIXTURES / name, encoding="utf-8") as fp:
        return json.load(fp)


@pytest.fixture
def manifest_v2() -> Dict[str, Any]:
    return load_fixture("manifest_v2.json")


@pytest.fixture
def manifest_v3() -> Dict[str, Any]:
    return load_fixture("manifest_v3.json")


@pytest.fixture
def collection_v3() -> Dict[str, Any]:
    return load_fixture("collection_v3.json")


@pytest.fixture
def collection_v2() -> Dict[str, Any]:
    return load_fixture("collection_v2.json")


class FakeResponse:
    def __init__(self, *, json_data: Any = None, content: bytes = b"", status: int = 200):
        self._json = json_data
        self.content = content
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no json body")
        return self._json

    def iter_content(self, chunk_size: int = 1024):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]


class FakeSession:
    """Minimal stand-in for ``requests.Session`` — records every GET."""

    def __init__(self, routes: Dict[str, Any], *, image_bytes: bytes = b"IMAGE"):
        self.routes = routes
        self.image_bytes = image_bytes
        self.calls: List[str] = []
        self.failures: Dict[str, int] = {}

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(url)
        if url in self.failures:
            return FakeResponse(status=self.failures[url])
        if url in self.routes:
            return FakeResponse(json_data=self.routes[url])
        return FakeResponse(content=self.image_bytes)


@pytest.fixture
def fake_session_factory():
    return FakeSession
