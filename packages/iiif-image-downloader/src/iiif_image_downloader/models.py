"""Dataclasses shared across the package.

The parsing layer (:mod:`iiif_image_downloader.manifest`) turns a IIIF
Presentation API document — version 2.x or 3.0 — into these version-neutral
objects, so the download layer never has to care which version it came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class ImageService:
    """A IIIF Image API service attached to a painting resource.

    ``version`` is the Image API major version (1, 2 or 3). It decides the
    default ``size`` segment of the image request: the Image API 3.0 dropped
    ``full`` in favour of ``max``.
    """

    id: str
    version: int = 2

    @property
    def default_size(self) -> str:
        return "max" if self.version >= 3 else "full"


@dataclass(frozen=True)
class CanvasImage:
    """One downloadable image, with enough context to name the output file."""

    index: int
    """0-based position of the canvas inside its manifest."""

    canvas_id: str
    label: Optional[str]
    image_id: Optional[str]
    """Direct URL of the painting resource (may be ``None`` for service-only bodies)."""

    service: Optional[ImageService] = None
    width: Optional[int] = None
    height: Optional[int] = None
    format: Optional[str] = None
    """Media type declared by the manifest, e.g. ``image/jpeg``."""


@dataclass(frozen=True)
class Manifest:
    """A parsed IIIF Manifest."""

    id: str
    label: Optional[str]
    presentation_version: int
    """Presentation API major version: 2 or 3."""

    images: List[CanvasImage] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.images)


@dataclass
class DownloadResult:
    """Outcome for a single image."""

    image: CanvasImage
    url: str
    path: Optional[str] = None
    status: str = "downloaded"
    """One of ``downloaded`` / ``skipped`` / ``failed`` / ``dry-run``."""

    error: Optional[str] = None


@dataclass
class ManifestReport:
    """Outcome for a whole manifest."""

    manifest_id: str
    label: Optional[str]
    presentation_version: int
    output_dir: Optional[str]
    results: List[DownloadResult] = field(default_factory=list)
    error: Optional[str] = None

    def _count(self, status: str) -> int:
        return sum(1 for r in self.results if r.status == status)

    @property
    def downloaded(self) -> int:
        return self._count("downloaded")

    @property
    def skipped(self) -> int:
        return self._count("skipped")

    @property
    def failed(self) -> int:
        return self._count("failed")

    @property
    def ok(self) -> bool:
        return self.error is None and self.failed == 0


@dataclass
class DownloadReport:
    """Outcome for an entire run (one or more manifests)."""

    manifests: List[ManifestReport] = field(default_factory=list)

    @property
    def downloaded(self) -> int:
        return sum(m.downloaded for m in self.manifests)

    @property
    def skipped(self) -> int:
        return sum(m.skipped for m in self.manifests)

    @property
    def failed(self) -> int:
        return sum(m.failed for m in self.manifests)

    @property
    def ok(self) -> bool:
        return all(m.ok for m in self.manifests)

    def summary(self) -> str:
        return (
            f"manifests={len(self.manifests)} "
            f"downloaded={self.downloaded} skipped={self.skipped} failed={self.failed}"
        )
