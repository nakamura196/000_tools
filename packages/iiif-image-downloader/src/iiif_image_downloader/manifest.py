"""Parsing of IIIF Presentation API documents (2.x and 3.0).

The two versions describe the same thing with different shapes:

* **2.x** — ``manifest.sequences[0].canvases[].images[].resource`` , where the
  resource carries ``@id`` and optionally a ``service`` (Image API).
* **3.0** — ``manifest.items[]`` (Canvas) → ``items[]`` (AnnotationPage) →
  ``items[]`` (Annotation with ``motivation: painting``) → ``body`` , where the
  body carries ``id`` and optionally a ``service`` list.

Everything here is pure: it takes a ``dict`` and returns
:class:`~iiif_image_downloader.models.Manifest`. Network access lives in
:func:`fetch_json` / :func:`load_manifest` so the parsers stay easy to test.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .errors import ManifestFetchError, ManifestParseError, UnsupportedVersionError
from .models import CanvasImage, ImageService, Manifest

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_USER_AGENT = "iiif-image-downloader (+https://github.com/nakamura196/000_tools)"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def _as_list(value: Any) -> List[Any]:
    """Wrap a scalar in a list; ``None`` becomes ``[]``."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _first_str(value: Any) -> Optional[str]:
    """Return the first string found in ``value`` (scalar, list or dict)."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            found = _first_str(item)
            if found:
                return found
        return None
    if isinstance(value, dict):
        # 2.x language-map entry: {"@value": "...", "@language": "ja"}
        if "@value" in value:
            return _first_str(value["@value"])
        # 3.0 language map: {"ja": ["..."], "none": ["..."]}
        for key in ("ja", "en", "none"):
            if key in value:
                return _first_str(value[key])
        for item in value.values():
            found = _first_str(item)
            if found:
                return found
    return None


def pick_label(value: Any) -> Optional[str]:
    """Extract a display label from a 2.x string/array or a 3.0 language map."""
    label = _first_str(value)
    return label.strip() if isinstance(label, str) and label.strip() else None


def _resource_id(node: Dict[str, Any]) -> Optional[str]:
    """Read the identifier of a node, tolerating both ``id`` and ``@id``."""
    for key in ("id", "@id"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _types(node: Dict[str, Any]) -> List[str]:
    """Return the declared types of a node (``type`` in 3.0, ``@type`` in 2.x)."""
    values: List[str] = []
    for key in ("type", "@type"):
        for item in _as_list(node.get(key)):
            if isinstance(item, str):
                values.append(item)
    return values


def _image_api_version(service: Dict[str, Any]) -> int:
    """Infer the Image API major version from a service description.

    Order of evidence: the 3.0 ``type`` (``ImageService3``), then the profile
    URI / compliance level string used by 1.x and 2.x. Unknown services fall
    back to 2, whose ``full`` size segment is the safest default for older
    servers.
    """
    for declared in _types(service):
        if declared.startswith("ImageService"):
            suffix = declared[len("ImageService") :]
            if suffix.isdigit():
                return int(suffix)

    profiles = " ".join(
        p if isinstance(p, str) else _first_str(p) or "" for p in _as_list(service.get("profile"))
    )
    if "image/3/" in profiles or profiles.startswith("level"):
        # 1.x and 2.x always spell the profile as a URI; a bare "level2"
        # string is the 3.0 form.
        return 3
    if "image/2/" in profiles:
        return 2
    if "image/1/" in profiles:
        return 1

    context = " ".join(c for c in _as_list(service.get("@context")) if isinstance(c, str))
    if "image/3/context.json" in context:
        return 3
    if "image/2/context.json" in context:
        return 2
    return 2


def _pick_service(node: Dict[str, Any]) -> Optional[ImageService]:
    """Return the Image API service of a painting resource, if any.

    ``service`` may be a dict (2.x) or a list (3.0, and some 2.x manifests).
    Non-image services (e.g. a search service accidentally attached to the
    resource) are ignored.
    """
    for key in ("service", "services"):
        for candidate in _as_list(node.get(key)):
            if not isinstance(candidate, dict):
                continue
            service_id = _resource_id(candidate)
            if not service_id:
                continue
            declared = " ".join(_types(candidate))
            profiles = " ".join(
                p if isinstance(p, str) else _first_str(p) or ""
                for p in _as_list(candidate.get("profile"))
            )
            looks_like_image = (
                declared.startswith("ImageService")
                or "iiif.io/api/image" in profiles
                or "iiif.io/api/image"
                in " ".join(c for c in _as_list(candidate.get("@context")) if isinstance(c, str))
                or (declared == "" and profiles == "")
            )
            if not looks_like_image:
                continue
            return ImageService(
                id=service_id.rstrip("/"),
                version=_image_api_version(candidate),
            )
    return None


def _int_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) else None


# --------------------------------------------------------------------------
# version detection
# --------------------------------------------------------------------------
def detect_presentation_version(data: Dict[str, Any]) -> int:
    """Return the Presentation API major version of ``data`` (2 or 3)."""
    contexts = [c for c in _as_list(data.get("@context")) if isinstance(c, str)]
    for context in contexts:
        if "presentation/3/context.json" in context:
            return 3
        if "presentation/2/context.json" in context:
            return 2

    declared = _types(data)
    if any(t.startswith("sc:") or t.startswith("oa:") for t in declared):
        return 2
    if "sequences" in data:
        return 2
    if "items" in data:
        return 3
    raise UnsupportedVersionError(
        "Could not determine the IIIF Presentation API version of the document"
    )


def is_collection(data: Dict[str, Any]) -> bool:
    return any(t in ("Collection", "sc:Collection") for t in _types(data))


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------
def _parse_v2(data: Dict[str, Any]) -> List[CanvasImage]:
    canvases: List[Any] = []
    for sequence in _as_list(data.get("sequences")):
        if isinstance(sequence, dict):
            canvases.extend(_as_list(sequence.get("canvases")))
    if not canvases:
        # Rare but legal: a manifest that inlines canvases without a sequence.
        canvases = _as_list(data.get("canvases"))

    images: List[CanvasImage] = []
    for index, canvas in enumerate(canvases):
        if not isinstance(canvas, dict):
            continue
        resource: Optional[Dict[str, Any]] = None
        for annotation in _as_list(canvas.get("images")):
            if isinstance(annotation, dict) and isinstance(annotation.get("resource"), dict):
                resource = annotation["resource"]
                break
        if resource is None:
            logger.debug("canvas %s has no painting resource; skipped", index)
            continue

        # A Choice wraps the real resources in "item"; take the first.
        if "item" in resource and not _resource_id(resource):
            items = [i for i in _as_list(resource.get("item")) if isinstance(i, dict)]
            if items:
                resource = items[0]

        images.append(
            CanvasImage(
                index=index,
                canvas_id=_resource_id(canvas) or f"canvas-{index}",
                label=pick_label(canvas.get("label")),
                image_id=_resource_id(resource),
                service=_pick_service(resource),
                width=_int_or_none(resource.get("width")) or _int_or_none(canvas.get("width")),
                height=_int_or_none(resource.get("height")) or _int_or_none(canvas.get("height")),
                format=resource.get("format") if isinstance(resource.get("format"), str) else None,
            )
        )
    return images


def _painting_bodies(canvas: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield the painting bodies of a 3.0 Canvas, unwrapping Choice bodies."""
    for page in _as_list(canvas.get("items")):
        if not isinstance(page, dict):
            continue
        for annotation in _as_list(page.get("items")):
            if not isinstance(annotation, dict):
                continue
            motivation = " ".join(
                m for m in _as_list(annotation.get("motivation")) if isinstance(m, str)
            )
            if motivation and "painting" not in motivation:
                continue
            for body in _as_list(annotation.get("body")):
                if not isinstance(body, dict):
                    continue
                if "Choice" in _types(body):
                    for choice in _as_list(body.get("items")):
                        if isinstance(choice, dict):
                            yield choice
                else:
                    yield body


def _parse_v3(data: Dict[str, Any]) -> List[CanvasImage]:
    images: List[CanvasImage] = []
    canvases = [
        c
        for c in _as_list(data.get("items"))
        if isinstance(c, dict) and (not _types(c) or "Canvas" in _types(c))
    ]

    for index, canvas in enumerate(canvases):
        body = None
        for candidate in _painting_bodies(canvas):
            types = _types(candidate)
            if types and "Image" not in types:
                continue
            body = candidate
            break
        if body is None:
            logger.debug("canvas %s has no painting Image body; skipped", index)
            continue

        images.append(
            CanvasImage(
                index=index,
                canvas_id=_resource_id(canvas) or f"canvas-{index}",
                label=pick_label(canvas.get("label")),
                image_id=_resource_id(body),
                service=_pick_service(body),
                width=_int_or_none(body.get("width")) or _int_or_none(canvas.get("width")),
                height=_int_or_none(body.get("height")) or _int_or_none(canvas.get("height")),
                format=body.get("format") if isinstance(body.get("format"), str) else None,
            )
        )
    return images


def parse_manifest(data: Dict[str, Any], *, source_uri: Optional[str] = None) -> Manifest:
    """Turn a Presentation API 2.x or 3.0 Manifest ``dict`` into a :class:`Manifest`."""
    if not isinstance(data, dict):
        raise ManifestParseError("Manifest must be a JSON object")
    if is_collection(data):
        raise ManifestParseError(
            "This document is a Collection, not a Manifest. "
            "Use collection_manifest_uris() to expand it first."
        )

    version = detect_presentation_version(data)
    images = _parse_v2(data) if version == 2 else _parse_v3(data)

    manifest = Manifest(
        id=_resource_id(data) or source_uri or "",
        label=pick_label(data.get("label")),
        presentation_version=version,
        images=images,
    )
    if not images:
        logger.warning("no images found in manifest %s", manifest.id or source_uri)
    return manifest


def collection_manifest_uris(data: Dict[str, Any]) -> List[str]:
    """Return the Manifest URIs directly contained in a Collection.

    Nested Collections are returned as-is; :func:`load_manifests` expands them
    recursively.
    """
    members: List[Any] = []
    members.extend(_as_list(data.get("manifests")))  # 2.x
    members.extend(_as_list(data.get("collections")))  # 2.x
    members.extend(_as_list(data.get("items")))  # 3.0
    members.extend(_as_list(data.get("members")))  # 2.1 mixed membership

    uris: List[str] = []
    for member in members:
        if not isinstance(member, dict):
            continue
        uri = _resource_id(member)
        if uri and uri not in uris:
            uris.append(uri)
    return uris


# --------------------------------------------------------------------------
# network
# --------------------------------------------------------------------------
def fetch_json(
    uri: str,
    *,
    session: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Dict[str, Any]:
    """GET ``uri`` and decode it as JSON.

    ``session`` may be any object with a ``get(url, timeout=..., headers=...)``
    method — a :class:`requests.Session` in practice, a stub in the tests.
    """
    if session is None:
        from .http import build_session

        session = build_session(user_agent=user_agent)

    try:
        response = session.get(uri, timeout=timeout, headers={"Accept": "application/json"})
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - re-raised as a package error
        raise ManifestFetchError(f"Failed to fetch {uri}: {exc}") from exc

    try:
        return response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise ManifestFetchError(f"{uri} did not return valid JSON: {exc}") from exc


def load_manifest(uri: str, **kwargs: Any) -> Manifest:
    """Fetch and parse a single Manifest."""
    return parse_manifest(fetch_json(uri, **kwargs), source_uri=uri)


def load_manifests(
    uris: Sequence[str],
    *,
    max_depth: int = 2,
    **kwargs: Any,
) -> List[Manifest]:
    """Fetch and parse several URIs, expanding Collections along the way.

    ``max_depth`` bounds Collection recursion (1 = expand the given Collection
    only). Duplicate URIs are visited once.
    """
    manifests: List[Manifest] = []
    seen = set()
    queue = [(uri, 0) for uri in uris]

    while queue:
        uri, depth = queue.pop(0)
        if uri in seen:
            continue
        seen.add(uri)

        data = fetch_json(uri, **kwargs)
        if is_collection(data):
            if depth >= max_depth:
                logger.warning("collection depth limit reached, not expanding %s", uri)
                continue
            children = collection_manifest_uris(data)
            logger.info("collection %s -> %d member(s)", uri, len(children))
            queue.extend((child, depth + 1) for child in children)
            continue

        manifests.append(parse_manifest(data, source_uri=uri))

    return manifests
