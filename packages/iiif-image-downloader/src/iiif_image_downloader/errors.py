"""Exception types raised by :mod:`iiif_image_downloader`."""

from __future__ import annotations


class IIIFError(Exception):
    """Base class for every error raised by this package."""


class ManifestFetchError(IIIFError):
    """The manifest (or collection) could not be retrieved or parsed as JSON."""


class ManifestParseError(IIIFError):
    """The document was valid JSON but did not look like a IIIF resource."""


class UnsupportedVersionError(ManifestParseError):
    """The document is IIIF, but of a Presentation API version we cannot read."""


class ImageDownloadError(IIIFError):
    """A single image could not be downloaded."""

    def __init__(self, url: str, message: str) -> None:
        super().__init__(f"{message}: {url}")
        self.url = url
        self.message = message
