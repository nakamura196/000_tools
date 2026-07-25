"""Downloading images described by a IIIF manifest."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence

from .errors import IIIFError, ImageDownloadError
from .imageapi import guess_extension, image_url, manifest_dirname, output_filename
from .manifest import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT, load_manifests
from .models import DownloadReport, DownloadResult, Manifest, ManifestReport

logger = logging.getLogger(__name__)

#: Seconds to wait between requests. Institutional IIIF servers are usually
#: modest in capacity, so the default is deliberately unhurried rather than
#: fast; lower it only for servers you operate.
DEFAULT_SLEEP = 1.0

CHUNK_SIZE = 64 * 1024


@dataclass
class DownloadOptions:
    """Everything that can be tuned for a run.

    Grouping the knobs here keeps the public functions to a couple of
    arguments and lets the CLI and the notebook build the same object.
    """

    output_dir: str = "data"
    limit: Optional[int] = None
    """Maximum images per manifest; ``None`` (or a negative value) means all."""

    size: Optional[str] = None
    """Image API size segment. ``None`` = ``max`` for v3, ``full`` for v2."""

    region: str = "full"
    rotation: str = "0"
    quality: str = "default"
    image_format: str = "jpg"

    sleep: float = DEFAULT_SLEEP
    timeout: int = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT
    retries: int = 3

    overwrite: bool = False
    """Re-download files that already exist instead of skipping them."""

    use_label: bool = False
    """Append the canvas label to each file name."""

    flat: bool = False
    """Write straight into ``output_dir`` instead of one folder per manifest."""

    dry_run: bool = False
    fail_fast: bool = False
    max_collection_depth: int = 2

    def normalized_limit(self) -> Optional[int]:
        if self.limit is None or self.limit < 0:
            return None
        return self.limit


ProgressFactory = Callable[[Iterable[Any], str, int], Iterable[Any]]


def _default_progress(iterable: Iterable[Any], desc: str, total: int) -> Iterable[Any]:
    """Wrap an iterable in a tqdm bar when tqdm is importable."""
    try:
        from tqdm.auto import tqdm
    except ImportError:  # pragma: no cover - tqdm is an optional convenience
        return iterable
    return tqdm(iterable, desc=desc, total=total)


def _download_to_file(session: Any, url: str, path: str, timeout: int) -> None:
    """Stream ``url`` into ``path``, writing to a temporary file first.

    Downloading via ``path + ".part"`` means an interrupted run never leaves a
    truncated image behind that a later run would mistake for complete and
    skip.
    """
    tmp_path = path + ".part"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        response = session.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        with open(tmp_path, "wb") as fp:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    fp.write(chunk)
        os.replace(tmp_path, path)
    except Exception as exc:  # noqa: BLE001 - normalized into a package error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise ImageDownloadError(url, str(exc)) from exc


def download_manifest(
    manifest: Manifest,
    options: Optional[DownloadOptions] = None,
    *,
    session: Any = None,
    progress: Optional[ProgressFactory] = _default_progress,
) -> ManifestReport:
    """Download the images of an already-parsed manifest."""
    options = options or DownloadOptions()
    if session is None and not options.dry_run:
        from .http import build_session

        session = build_session(user_agent=options.user_agent, retries=options.retries)

    limit = options.normalized_limit()
    targets = manifest.images[:limit] if limit is not None else manifest.images

    if options.flat:
        target_dir = options.output_dir
    else:
        target_dir = os.path.join(
            options.output_dir,
            manifest_dirname(manifest.id, label=manifest.label),
        )

    report = ManifestReport(
        manifest_id=manifest.id,
        label=manifest.label,
        presentation_version=manifest.presentation_version,
        output_dir=target_dir,
    )

    iterator: Iterable[Any] = targets
    if progress is not None and targets:
        iterator = progress(targets, manifest.label or manifest.id, len(targets))

    for image in iterator:
        try:
            url = image_url(
                image,
                size=options.size,
                region=options.region,
                rotation=options.rotation,
                quality=options.quality,
                image_format=options.image_format,
            )
        except ValueError as exc:
            report.results.append(
                DownloadResult(image=image, url="", status="failed", error=str(exc))
            )
            if options.fail_fast:
                raise IIIFError(str(exc)) from exc
            continue

        filename = output_filename(
            image,
            extension=guess_extension(url, image, default=options.image_format),
            use_label=options.use_label,
        )
        path = os.path.join(target_dir, filename)

        if options.dry_run:
            report.results.append(DownloadResult(image=image, url=url, path=path, status="dry-run"))
            continue

        if os.path.exists(path) and not options.overwrite:
            report.results.append(DownloadResult(image=image, url=url, path=path, status="skipped"))
            continue

        if options.sleep > 0:
            time.sleep(options.sleep)

        try:
            _download_to_file(session, url, path, options.timeout)
        except ImageDownloadError as exc:
            logger.warning("%s", exc)
            report.results.append(
                DownloadResult(image=image, url=url, path=path, status="failed", error=exc.message)
            )
            if options.fail_fast:
                raise
            continue

        report.results.append(DownloadResult(image=image, url=url, path=path, status="downloaded"))

    return report


def download(
    manifest_uris: Sequence[str],
    options: Optional[DownloadOptions] = None,
    *,
    session: Any = None,
    progress: Optional[ProgressFactory] = _default_progress,
) -> DownloadReport:
    """Fetch each URI (Manifest or Collection) and download its images.

    A manifest that cannot be fetched or parsed is recorded in the report and
    the run continues, unless ``options.fail_fast`` is set.
    """
    options = options or DownloadOptions()
    if session is None:
        from .http import build_session

        session = build_session(user_agent=options.user_agent, retries=options.retries)

    report = DownloadReport()

    try:
        manifests: List[Manifest] = load_manifests(
            manifest_uris,
            max_depth=options.max_collection_depth,
            session=session,
            timeout=options.timeout,
            user_agent=options.user_agent,
        )
    except IIIFError as exc:
        if options.fail_fast:
            raise
        logger.error("%s", exc)
        report.manifests.append(
            ManifestReport(
                manifest_id=", ".join(manifest_uris),
                label=None,
                presentation_version=0,
                output_dir=None,
                error=str(exc),
            )
        )
        return report

    for manifest in manifests:
        logger.info(
            "%s (Presentation API %d, %d canvas)",
            manifest.label or manifest.id,
            manifest.presentation_version,
            len(manifest),
        )
        report.manifests.append(
            download_manifest(manifest, options, session=session, progress=progress)
        )

    return report
