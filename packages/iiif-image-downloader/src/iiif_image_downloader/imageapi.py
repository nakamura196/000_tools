"""Image API request URLs and output file naming."""

from __future__ import annotations

import posixpath
import re
from typing import Optional
from urllib.parse import unquote, urlparse

from .models import CanvasImage

#: Media type -> file extension, for the formats the Image API can return.
FORMAT_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/tiff": "tif",
    "image/gif": "gif",
    "image/jp2": "jp2",
    "image/webp": "webp",
    "application/pdf": "pdf",
}

KNOWN_EXTENSIONS = set(FORMAT_EXTENSIONS.values()) | {"jpeg", "tiff"}

_UNSAFE = re.compile(r"[^0-9A-Za-z._-]+")


def image_url(
    image: CanvasImage,
    *,
    size: Optional[str] = None,
    region: str = "full",
    rotation: str = "0",
    quality: str = "default",
    image_format: str = "jpg",
) -> str:
    """Build the URL to download for one canvas.

    When the resource has a Image API service, a full request URI is assembled
    (``{id}/{region}/{size}/{rotation}/{quality}.{format}``). ``size`` defaults
    to ``max`` for Image API 3 and ``full`` for 1.x/2.x — the 3.0 spec removed
    ``full``, while some 2.x servers never implemented ``max``.

    Without a service the manifest only offers a plain image URL, which is
    returned unchanged; ``size`` and friends cannot apply in that case.
    """
    if image.service is not None:
        resolved_size = size or image.service.default_size
        return "{base}/{region}/{size}/{rotation}/{quality}.{fmt}".format(
            base=image.service.id.rstrip("/"),
            region=region,
            size=resolved_size,
            rotation=rotation,
            quality=quality,
            fmt=image_format,
        )
    if image.image_id:
        return image.image_id
    raise ValueError(f"canvas {image.canvas_id} has neither a service nor an image id")


def _slugify(text: str, *, max_length: int = 80) -> str:
    """Reduce arbitrary text to something safe to use as a path segment."""
    cleaned = _UNSAFE.sub("_", unquote(text)).strip("._-")
    cleaned = re.sub(r"_{2,}", "_", cleaned)
    return cleaned[:max_length] or "untitled"


def manifest_dirname(manifest_id: str, *, label: Optional[str] = None) -> str:
    """Derive a readable output folder name from a manifest.

    Prefers the last meaningful path segment of the manifest URI (e.g.
    ``3437686`` for ``.../iiif/3437686/manifest.json``), which keeps folders
    short and stable, and falls back to the whole host+path or the label.
    """
    parsed = urlparse(manifest_id)
    segments = [s for s in parsed.path.split("/") if s]
    if segments and segments[-1] in ("manifest", "manifest.json", "info.json"):
        segments = segments[:-1]

    if segments:
        candidate = segments[-1]
        # Purely generic tails ("iiif", "api") carry no information on their own.
        if candidate.lower() in ("iiif", "api", "v2", "v3", "presentation") and len(segments) > 1:
            candidate = "_".join(segments[-2:])
        host = parsed.netloc.split(":")[0]
        return _slugify(f"{host}_{candidate}" if host else candidate)

    if label:
        return _slugify(label)
    return _slugify(manifest_id or "manifest")


def guess_extension(url: str, image: CanvasImage, default: str = "jpg") -> str:
    """Best-effort file extension for a downloaded image."""
    ext = posixpath.splitext(urlparse(url).path)[1].lstrip(".").lower()
    if ext in KNOWN_EXTENSIONS:
        return "jpg" if ext == "jpeg" else ("tif" if ext == "tiff" else ext)
    if image.format:
        mapped = FORMAT_EXTENSIONS.get(image.format.split(";")[0].strip().lower())
        if mapped:
            return mapped
    return default


def output_filename(
    image: CanvasImage,
    *,
    extension: str,
    use_label: bool = False,
    digits: int = 5,
) -> str:
    """Name one output file.

    The default is a zero-padded canvas number, which sorts correctly and never
    collides. ``use_label`` appends the canvas label for human-readable names
    while keeping the number as the sort key.
    """
    stem = str(image.index + 1).zfill(digits)
    if use_label and image.label:
        stem = f"{stem}_{_slugify(image.label, max_length=60)}"
    return f"{stem}.{extension}"
