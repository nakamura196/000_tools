"""Bulk image download from IIIF manifests (Presentation API 2.x / 3.0).

Typical use::

    from iiif_image_downloader import DownloadOptions, download

    report = download(
        ["https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json"],
        DownloadOptions(output_dir="data", limit=3, sleep=1.0),
    )
    print(report.summary())

Please respect the terms of use of the institution providing the images, and
keep ``sleep`` high enough not to burden their server.
"""

from __future__ import annotations

__version__ = "1.0.0"

from .downloader import DownloadOptions, download, download_manifest
from .errors import (
    IIIFError,
    ImageDownloadError,
    ManifestFetchError,
    ManifestParseError,
    UnsupportedVersionError,
)
from .imageapi import image_url, manifest_dirname, output_filename
from .manifest import (
    collection_manifest_uris,
    detect_presentation_version,
    is_collection,
    load_manifest,
    load_manifests,
    parse_manifest,
)
from .models import (
    CanvasImage,
    DownloadReport,
    DownloadResult,
    ImageService,
    Manifest,
    ManifestReport,
)

__all__ = [
    "__version__",
    "CanvasImage",
    "DownloadOptions",
    "DownloadReport",
    "DownloadResult",
    "IIIFError",
    "ImageDownloadError",
    "ImageService",
    "Manifest",
    "ManifestFetchError",
    "ManifestParseError",
    "ManifestReport",
    "UnsupportedVersionError",
    "collection_manifest_uris",
    "detect_presentation_version",
    "download",
    "download_manifest",
    "image_url",
    "is_collection",
    "load_manifest",
    "load_manifests",
    "manifest_dirname",
    "output_filename",
    "parse_manifest",
]
