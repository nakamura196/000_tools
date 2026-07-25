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

#: Characters that cannot appear in a path segment on macOS, Linux or Windows,
#: plus whitespace and control characters. Everything else — including Japanese
#: — is kept, so labels stay readable in the output folder.
_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f\s]+')

#: A leading dot hides the file; these names are reserved on Windows.
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


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
    to ``max`` for Image API 3 and ``full`` for 1.x/2.x — 3.0 removed ``full``
    as a *size* value, while ``max`` only arrived in 2.1 and is not understood
    by earlier servers. (``full`` remains the ordinary *region* value in 3.0.)

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
    """Reduce arbitrary text to something safe to use as a path segment.

    Only characters that a file system would reject (or that make a name
    ambiguous) are replaced. Japanese and other non-ASCII text survives, since
    most of the material this package is pointed at is labelled in Japanese and
    ``00001_1丁表.jpg`` is far more useful than ``00001_untitled.jpg``.

    ``..`` and a leading ``.`` are neutralised, so a hostile label cannot climb
    out of the output directory or produce a hidden file.
    """
    cleaned = _UNSAFE.sub("_", unquote(text))
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("._-")
    cleaned = cleaned[:max_length].strip("._-")
    if not cleaned or set(cleaned) <= {"."}:
        return "untitled"
    if cleaned.lower() in _RESERVED:
        return f"{cleaned}_"
    return cleaned


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
        # Servers that name the file after the item (".../manifest-01.json",
        # ".../<uuid>.json") would otherwise carry the suffix into the folder.
        for suffix in (".jsonld", ".json"):
            if candidate.lower().endswith(suffix) and len(candidate) > len(suffix):
                candidate = candidate[: -len(suffix)]
                break
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

    The default is a zero-padded canvas number, which sorts correctly and is
    unique within one manifest — callers writing several manifests into one
    directory must add their own prefix. ``use_label`` appends the canvas label
    for human-readable names while keeping the number as the sort key.
    """
    stem = str(image.index + 1).zfill(digits)
    if use_label and image.label:
        stem = f"{stem}_{_slugify(image.label, max_length=60)}"
    return f"{stem}.{extension}"
