from __future__ import annotations

import pytest

from iiif_image_downloader import CanvasImage, ImageService, image_url, manifest_dirname
from iiif_image_downloader.imageapi import guess_extension, output_filename


def make_image(**kwargs):
    defaults = dict(
        index=0,
        canvas_id="https://example.org/canvas/p1",
        label=None,
        image_id="https://example.org/static/p1.jpg",
        service=None,
    )
    defaults.update(kwargs)
    return CanvasImage(**defaults)


class TestImageUrl:
    def test_image_api_2_defaults_to_full(self):
        image = make_image(service=ImageService(id="https://example.org/iiif/a", version=2))
        assert image_url(image) == "https://example.org/iiif/a/full/full/0/default.jpg"

    def test_image_api_3_defaults_to_max(self):
        image = make_image(service=ImageService(id="https://example.org/iiif/a", version=3))
        assert image_url(image) == "https://example.org/iiif/a/full/max/0/default.jpg"

    def test_explicit_size_wins(self):
        image = make_image(service=ImageService(id="https://example.org/iiif/a", version=3))
        assert image_url(image, size="!1024,1024").endswith("/full/!1024,1024/0/default.jpg")

    def test_all_segments_configurable(self):
        image = make_image(service=ImageService(id="https://example.org/iiif/a", version=3))
        url = image_url(
            image,
            region="0,0,100,100",
            size="200,",
            rotation="90",
            quality="gray",
            image_format="png",
        )
        assert url == "https://example.org/iiif/a/0,0,100,100/200,/90/gray.png"

    def test_without_service_returns_direct_url(self):
        assert image_url(make_image()) == "https://example.org/static/p1.jpg"

    def test_without_service_or_id_raises(self):
        with pytest.raises(ValueError):
            image_url(make_image(image_id=None))


class TestManifestDirname:
    def test_uses_last_meaningful_segment(self):
        assert (
            manifest_dirname("https://www.dl.ndl.go.jp/api/iiif/3437686/manifest.json")
            == "www.dl.ndl.go.jp_3437686"
        )

    def test_manifest_json_suffix_stripped(self):
        assert manifest_dirname("https://example.org/item/999/manifest") == "example.org_999"

    def test_generic_tail_gets_more_context(self):
        assert manifest_dirname("https://example.org/foo/iiif") == "example.org_foo_iiif"

    def test_falls_back_to_label(self):
        assert manifest_dirname("", label="源氏物語 サンプル") == "untitled"

    def test_result_is_path_safe(self):
        name = manifest_dirname("https://example.org/a b/c%2Fd/manifest.json")
        assert "/" not in name and " " not in name


class TestFilenames:
    def test_zero_padded_index(self):
        assert output_filename(make_image(index=4), extension="jpg") == "00005.jpg"

    def test_label_appended_on_request(self):
        name = output_filename(make_image(index=0, label="2丁 表"), extension="jpg", use_label=True)
        assert name.startswith("00001_")
        assert name.endswith(".jpg")

    def test_extension_from_url(self):
        assert guess_extension("https://example.org/a/b.png", make_image()) == "png"

    def test_extension_from_declared_format(self):
        image = make_image(format="image/tiff")
        assert guess_extension("https://example.org/a/b", image) == "tif"

    def test_extension_falls_back_to_default(self):
        assert guess_extension("https://example.org/a/b", make_image()) == "jpg"
