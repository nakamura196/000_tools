from __future__ import annotations

import os

import pytest

from iiif_image_downloader import DownloadOptions, download, download_manifest, parse_manifest


def options(tmp_path, **kwargs):
    defaults = dict(output_dir=str(tmp_path), sleep=0)
    defaults.update(kwargs)
    return DownloadOptions(**defaults)


class TestDownloadManifest:
    def test_writes_one_file_per_canvas(self, tmp_path, fake_session_factory, manifest_v3):
        manifest = parse_manifest(manifest_v3)
        session = fake_session_factory({})
        report = download_manifest(manifest, options(tmp_path), session=session, progress=None)

        assert report.downloaded == 3
        assert report.ok
        written = sorted(os.listdir(report.output_dir))
        assert written == ["00001.jpg", "00002.tif", "00003.jpg"]

    def test_limit_truncates(self, tmp_path, fake_session_factory, manifest_v3):
        report = download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path, limit=1),
            session=fake_session_factory({}),
            progress=None,
        )
        assert report.downloaded == 1

    def test_negative_limit_means_all(self, tmp_path, fake_session_factory, manifest_v3):
        report = download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path, limit=-1),
            session=fake_session_factory({}),
            progress=None,
        )
        assert report.downloaded == 3

    def test_existing_files_are_skipped(self, tmp_path, fake_session_factory, manifest_v3):
        manifest = parse_manifest(manifest_v3)
        session = fake_session_factory({})
        download_manifest(manifest, options(tmp_path), session=session, progress=None)
        again = download_manifest(manifest, options(tmp_path), session=session, progress=None)
        assert again.skipped == 3
        assert again.downloaded == 0

    def test_overwrite_redownloads(self, tmp_path, fake_session_factory, manifest_v3):
        manifest = parse_manifest(manifest_v3)
        session = fake_session_factory({})
        download_manifest(manifest, options(tmp_path), session=session, progress=None)
        again = download_manifest(
            manifest, options(tmp_path, overwrite=True), session=session, progress=None
        )
        assert again.downloaded == 3

    def test_v3_requests_max_size(self, tmp_path, fake_session_factory, manifest_v3):
        session = fake_session_factory({})
        download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path, limit=1),
            session=session,
            progress=None,
        )
        assert session.calls == ["https://example.org/iiif/67890_1/full/max/0/default.jpg"]

    def test_v2_requests_full_size(self, tmp_path, fake_session_factory, manifest_v2):
        session = fake_session_factory({})
        download_manifest(
            parse_manifest(manifest_v2),
            options(tmp_path, limit=1),
            session=session,
            progress=None,
        )
        assert session.calls == ["https://example.org/iiif/12345_1/full/full/0/default.jpg"]

    def test_failure_is_recorded_and_run_continues(
        self, tmp_path, fake_session_factory, manifest_v3
    ):
        session = fake_session_factory({})
        session.failures["https://example.org/iiif/67890_1/full/max/0/default.jpg"] = 500
        report = download_manifest(
            parse_manifest(manifest_v3), options(tmp_path), session=session, progress=None
        )
        assert report.failed == 1
        assert report.downloaded == 2
        assert not report.ok

    def test_failed_download_leaves_no_partial_file(
        self, tmp_path, fake_session_factory, manifest_v3
    ):
        session = fake_session_factory({})
        session.failures["https://example.org/iiif/67890_1/full/max/0/default.jpg"] = 500
        report = download_manifest(
            parse_manifest(manifest_v3), options(tmp_path), session=session, progress=None
        )
        assert not os.path.exists(os.path.join(report.output_dir, "00001.jpg"))
        assert not os.path.exists(os.path.join(report.output_dir, "00001.jpg.part"))

    def test_dry_run_writes_nothing(self, tmp_path, fake_session_factory, manifest_v3):
        session = fake_session_factory({})
        report = download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path, dry_run=True),
            session=session,
            progress=None,
        )
        assert session.calls == []
        assert not os.path.exists(report.output_dir)
        assert all(r.status == "dry-run" for r in report.results)

    def test_unwritable_output_is_a_package_error(
        self, tmp_path, fake_session_factory, manifest_v3
    ):
        # An output path whose parent is a regular file must be reported, not
        # escape as a bare OSError the CLI does not catch.
        blocker = tmp_path / "blocked"
        blocker.write_text("not a directory")
        report = download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path / "blocked", limit=1),
            session=fake_session_factory({}),
            progress=None,
        )
        assert report.failed == 1
        assert report.results[0].error

    def test_keyboard_interrupt_leaves_no_partial_file(
        self, tmp_path, fake_session_factory, manifest_v3
    ):
        session = fake_session_factory({})
        url = "https://example.org/iiif/67890_1/full/max/0/default.jpg"

        original_get = session.get

        def interrupting_get(target, **kwargs):
            if target == url:
                raise KeyboardInterrupt
            return original_get(target, **kwargs)

        session.get = interrupting_get

        with pytest.raises(KeyboardInterrupt):
            download_manifest(
                parse_manifest(manifest_v3),
                options(tmp_path, limit=1),
                session=session,
                progress=None,
            )
        leftovers = list((tmp_path).rglob("*.part"))
        assert leftovers == []

    def test_flat_layout(self, tmp_path, fake_session_factory, manifest_v3):
        report = download_manifest(
            parse_manifest(manifest_v3),
            options(tmp_path, flat=True),
            session=fake_session_factory({}),
            progress=None,
        )
        assert report.output_dir == str(tmp_path)


class TestDownload:
    def test_collection_expanded_end_to_end(
        self, tmp_path, fake_session_factory, manifest_v2, manifest_v3, collection_v3
    ):
        session = fake_session_factory(
            {
                "https://example.org/api/iiif/collection/top": collection_v3,
                "https://example.org/api/iiif/67890/manifest.json": manifest_v3,
                "https://example.org/api/iiif/12345/manifest.json": manifest_v2,
            }
        )
        report = download(
            ["https://example.org/api/iiif/collection/top"],
            options(tmp_path),
            session=session,
            progress=None,
        )
        assert len(report.manifests) == 2
        assert report.downloaded == 5  # 3 canvases in v3 + 2 in v2
        assert report.ok

    def test_separate_folder_per_manifest(
        self, tmp_path, fake_session_factory, manifest_v2, manifest_v3, collection_v3
    ):
        session = fake_session_factory(
            {
                "https://example.org/api/iiif/collection/top": collection_v3,
                "https://example.org/api/iiif/67890/manifest.json": manifest_v3,
                "https://example.org/api/iiif/12345/manifest.json": manifest_v2,
            }
        )
        download(
            ["https://example.org/api/iiif/collection/top"],
            options(tmp_path),
            session=session,
            progress=None,
        )
        assert sorted(os.listdir(tmp_path)) == ["example.org_12345", "example.org_67890"]

    def test_unreachable_manifest_is_reported_not_raised(self, tmp_path, fake_session_factory):
        session = fake_session_factory({})
        session.failures["https://example.org/missing/manifest.json"] = 404
        report = download(
            ["https://example.org/missing/manifest.json"],
            options(tmp_path),
            session=session,
            progress=None,
        )
        assert not report.ok
        assert report.manifests[0].error is not None

    def test_one_bad_manifest_does_not_abort_the_others(
        self, tmp_path, fake_session_factory, manifest_v3
    ):
        session = fake_session_factory(
            {"https://example.org/api/iiif/67890/manifest.json": manifest_v3}
        )
        session.failures["https://example.org/missing/manifest.json"] = 404
        report = download(
            [
                "https://example.org/missing/manifest.json",
                "https://example.org/api/iiif/67890/manifest.json",
            ],
            options(tmp_path),
            session=session,
            progress=None,
        )
        assert report.downloaded == 3
        assert not report.ok
        errors = [m for m in report.manifests if m.error]
        assert len(errors) == 1
        assert errors[0].manifest_id == "https://example.org/missing/manifest.json"

    def test_colliding_folder_names_are_disambiguated(
        self, tmp_path, fake_session_factory, manifest_v2, manifest_v3
    ):
        # Both manifests slugify to "example.org_1" without disambiguation.
        manifest_v2["@id"] = "https://example.org/a/1/manifest.json"
        manifest_v3["id"] = "https://example.org/b/1/manifest.json"
        session = fake_session_factory(
            {
                "https://example.org/a/1/manifest.json": manifest_v2,
                "https://example.org/b/1/manifest.json": manifest_v3,
            }
        )
        report = download(
            ["https://example.org/a/1/manifest.json", "https://example.org/b/1/manifest.json"],
            options(tmp_path),
            session=session,
            progress=None,
        )
        dirs = {m.output_dir for m in report.manifests}
        assert len(dirs) == 2
        assert report.downloaded == 5
        assert report.skipped == 0

    def test_flat_mode_does_not_collide_across_manifests(
        self, tmp_path, fake_session_factory, manifest_v2, manifest_v3
    ):
        session = fake_session_factory(
            {
                "https://example.org/api/iiif/12345/manifest.json": manifest_v2,
                "https://example.org/api/iiif/67890/manifest.json": manifest_v3,
            }
        )
        report = download(
            [
                "https://example.org/api/iiif/12345/manifest.json",
                "https://example.org/api/iiif/67890/manifest.json",
            ],
            options(tmp_path, flat=True),
            session=session,
            progress=None,
        )
        assert report.downloaded == 5
        assert report.skipped == 0
        assert report.ok
        assert len(os.listdir(tmp_path)) == 5
