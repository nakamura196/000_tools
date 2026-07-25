"""Command line interface: ``iiif-image-download``."""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from . import __version__
from .downloader import DEFAULT_SLEEP, DownloadOptions, download
from .errors import IIIFError
from .manifest import DEFAULT_TIMEOUT, DEFAULT_USER_AGENT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iiif-image-download",
        description=(
            "Download the images of a IIIF manifest (Presentation API 2.x / 3.0). "
            "Please respect the terms of use of the providing institution."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "uris",
        nargs="*",
        metavar="URI",
        help="Manifest or Collection URI (repeatable)",
    )
    parser.add_argument(
        "-f",
        "--from-file",
        metavar="PATH",
        help="Read URIs from a text file, one per line (# starts a comment)",
    )
    parser.add_argument("-o", "--output-dir", default="data", help="Output directory")
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=-1,
        help="Maximum images per manifest (-1 for all)",
    )
    parser.add_argument(
        "--size",
        default=None,
        help="Image API size, e.g. max / full / 1000, / !1024,1024 "
        "(default: max for Image API 3, full for 1.x-2.x)",
    )
    parser.add_argument("--region", default="full", help="Image API region")
    parser.add_argument("--rotation", default="0", help="Image API rotation")
    parser.add_argument("--quality", default="default", help="Image API quality")
    parser.add_argument("--format", dest="image_format", default="jpg", help="Image API format")
    parser.add_argument(
        "-s",
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP,
        help="Seconds to wait before each image request",
    )
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout")
    parser.add_argument("--retries", type=int, default=3, help="Retries on 429/5xx")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header")
    parser.add_argument("--overwrite", action="store_true", help="Re-download existing files")
    parser.add_argument(
        "--use-label", action="store_true", help="Append the canvas label to file names"
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Write into the output directory directly (no per-manifest folder)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List the URLs without downloading")
    parser.add_argument("--fail-fast", action="store_true", help="Stop at the first failure")
    parser.add_argument(
        "--max-collection-depth",
        type=int,
        default=2,
        help="How deep to expand nested Collections",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Only report warnings")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _read_uri_file(path: str) -> List[str]:
    uris: List[str] = []
    with open(path, encoding="utf-8") as fp:
        for raw in fp:
            line = raw.split("#", 1)[0].strip()
            if line:
                uris.append(line)
    return uris


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else (logging.WARNING if args.quiet else logging.INFO),
        format="%(levelname)s: %(message)s",
    )

    uris = list(args.uris)
    if args.from_file:
        uris.extend(_read_uri_file(args.from_file))
    if not uris:
        print("error: no manifest URI given (pass URIs or --from-file)", file=sys.stderr)
        return 2

    options = DownloadOptions(
        output_dir=args.output_dir,
        limit=args.limit,
        size=args.size,
        region=args.region,
        rotation=args.rotation,
        quality=args.quality,
        image_format=args.image_format,
        sleep=args.sleep,
        timeout=args.timeout,
        user_agent=args.user_agent,
        retries=args.retries,
        overwrite=args.overwrite,
        use_label=args.use_label,
        flat=args.flat,
        dry_run=args.dry_run,
        fail_fast=args.fail_fast,
        max_collection_depth=args.max_collection_depth,
    )

    try:
        report = download(uris, options)
    except IIIFError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        # Interrupting is a documented way to stop a long run; re-running the
        # same command picks up where it left off, so say so instead of
        # dumping a traceback.
        print(
            "\ninterrupted. Re-run the same command to resume "
            "(already downloaded files are skipped).",
            file=sys.stderr,
        )
        return 130

    if args.dry_run:
        for manifest_report in report.manifests:
            for result in manifest_report.results:
                print(f"{result.url}\t{result.path}")

    print(report.summary(), file=sys.stderr)
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
