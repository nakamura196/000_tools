from __future__ import annotations

import pytest

from iiif_image_downloader import (
    ManifestParseError,
    UnsupportedVersionError,
    collection_manifest_uris,
    detect_presentation_version,
    is_collection,
    load_manifests,
    parse_manifest,
)
from iiif_image_downloader.manifest import pick_label


class TestVersionDetection:
    def test_v2_from_context(self, manifest_v2):
        assert detect_presentation_version(manifest_v2) == 2

    def test_v3_from_context(self, manifest_v3):
        assert detect_presentation_version(manifest_v3) == 3

    def test_v2_from_shape_without_context(self, manifest_v2):
        del manifest_v2["@context"]
        assert detect_presentation_version(manifest_v2) == 2

    def test_v3_from_shape_without_context(self, manifest_v3):
        del manifest_v3["@context"]
        del manifest_v3["type"]
        assert detect_presentation_version(manifest_v3) == 3

    def test_unknown_shape_raises(self):
        with pytest.raises(UnsupportedVersionError):
            detect_presentation_version({"foo": "bar"})


class TestLabels:
    def test_plain_string(self):
        assert pick_label("hello") == "hello"

    def test_v2_language_array(self):
        value = [{"@value": "second", "@language": "en"}, {"@value": "二", "@language": "ja"}]
        assert pick_label(value) == "second"

    def test_v3_language_map_prefers_japanese(self):
        assert pick_label({"en": ["Genji"], "ja": ["源氏"]}) == "源氏"

    def test_empty(self):
        assert pick_label(None) is None
        assert pick_label({}) is None


class TestParseV2:
    def test_basic(self, manifest_v2):
        manifest = parse_manifest(manifest_v2)
        assert manifest.presentation_version == 2
        assert manifest.label == "校異源氏物語 サンプル"
        # the third canvas has no painting annotation and is dropped
        assert len(manifest) == 2

    def test_image_service_detected(self, manifest_v2):
        image = parse_manifest(manifest_v2).images[0]
        assert image.service is not None
        assert image.service.id == "https://example.org/iiif/12345_1"
        assert image.service.version == 2
        assert image.width == 2000

    def test_canvas_without_service_keeps_direct_url(self, manifest_v2):
        image = parse_manifest(manifest_v2).images[1]
        assert image.service is None
        assert image.image_id == "https://example.org/static/12345_2.png"
        assert image.label == "second"

    def test_index_follows_canvas_order(self, manifest_v2):
        assert [i.index for i in parse_manifest(manifest_v2).images] == [0, 1]


class TestParseV3:
    def test_basic(self, manifest_v3):
        manifest = parse_manifest(manifest_v3)
        assert manifest.presentation_version == 3
        assert manifest.label == "源氏物語 サンプル v3"
        assert len(manifest) == 3

    def test_image_service_3(self, manifest_v3):
        image = parse_manifest(manifest_v3).images[0]
        assert image.service is not None
        assert image.service.id == "https://example.org/iiif/67890_1"
        assert image.service.version == 3
        assert image.service.default_size == "max"

    def test_choice_body_takes_first_item(self, manifest_v3):
        image = parse_manifest(manifest_v3).images[1]
        assert image.image_id == "https://example.org/static/67890_2.tif"
        assert image.service is None
        assert image.label == "2丁表"

    def test_image_service_2_inside_v3_manifest(self, manifest_v3):
        image = parse_manifest(manifest_v3).images[2]
        assert image.service is not None
        assert image.service.version == 2
        assert image.service.default_size == "full"

    def test_non_painting_annotation_ignored(self, manifest_v3):
        page = manifest_v3["items"][0]["items"][0]
        page["items"].insert(
            0,
            {
                "type": "Annotation",
                "motivation": "supplementing",
                "body": {"id": "https://example.org/text.txt", "type": "Text"},
            },
        )
        image = parse_manifest(manifest_v3).images[0]
        assert image.service is not None


class TestServiceDetection:
    def test_context_beats_bare_level_profile(self, manifest_v2):
        # An Image API 2 service written with the abbreviated 3.0-style profile
        # must still be treated as v2, or every request asks for /full/max/.
        resource = manifest_v2["sequences"][0]["canvases"][0]["images"][0]["resource"]
        resource["service"] = {
            "@context": "http://iiif.io/api/image/2/context.json",
            "@id": "https://example.org/iiif/12345_1",
            "profile": "level2",
        }
        image = parse_manifest(manifest_v2).images[0]
        assert image.service.version == 2

    def test_profile_as_list_is_understood(self, manifest_v2):
        # Conformant Image API 2.x info.json: profile is a list whose first
        # entry is the compliance level URI.
        resource = manifest_v2["sequences"][0]["canvases"][0]["images"][0]["resource"]
        resource["service"] = {
            "@id": "https://example.org/iiif/12345_1",
            "profile": [
                "http://iiif.io/api/image/2/level2.json",
                {"formats": ["jpg"], "supports": ["sizeByW"]},
            ],
        }
        image = parse_manifest(manifest_v2).images[0]
        assert image.service.version == 2

    def test_image_service_wins_over_other_services(self, manifest_v2):
        resource = manifest_v2["sequences"][0]["canvases"][0]["images"][0]["resource"]
        resource["service"] = [
            {"@id": "https://example.org/auth/login"},
            {
                "@id": "https://example.org/iiif/12345_1",
                "profile": "http://iiif.io/api/image/2/level2.json",
            },
        ]
        image = parse_manifest(manifest_v2).images[0]
        assert image.service.id == "https://example.org/iiif/12345_1"

    def test_sole_untyped_service_is_still_used(self, manifest_v2):
        resource = manifest_v2["sequences"][0]["canvases"][0]["images"][0]["resource"]
        resource["service"] = {"@id": "https://example.org/iiif/12345_1"}
        image = parse_manifest(manifest_v2).images[0]
        assert image.service.id == "https://example.org/iiif/12345_1"
        assert image.service.version == 2


class TestChoice:
    def test_v2_choice_prefers_default_over_alternative(self, manifest_v2):
        # A 2.x Choice puts the image to show in `default` and alternatives
        # (x-ray, ultraviolet…) in `item`.
        annotation = manifest_v2["sequences"][0]["canvases"][0]["images"][0]
        annotation["resource"] = {
            "@type": "oa:Choice",
            "default": {"@id": "https://example.org/color.jpg", "format": "image/jpeg"},
            "item": [{"@id": "https://example.org/xray.jpg", "format": "image/jpeg"}],
        }
        image = parse_manifest(manifest_v2).images[0]
        assert image.image_id == "https://example.org/color.jpg"

    def test_v2_choice_without_default_falls_back_to_item(self, manifest_v2):
        annotation = manifest_v2["sequences"][0]["canvases"][0]["images"][0]
        annotation["resource"] = {
            "@type": "oa:Choice",
            "item": [{"@id": "https://example.org/only.jpg"}],
        }
        image = parse_manifest(manifest_v2).images[0]
        assert image.image_id == "https://example.org/only.jpg"


class TestCanvasNumbering:
    def test_v3_non_canvas_entry_does_not_shift_numbering(self, manifest_v3):
        manifest_v3["items"].insert(0, {"id": "https://example.org/x", "type": "Range"})
        indexes = [image.index for image in parse_manifest(manifest_v3).images]
        assert indexes == [1, 2, 3]

    def test_v2_unpaintable_canvas_leaves_a_gap(self, manifest_v2):
        # Canvas 3 has no painting annotation; numbering follows canvas order.
        assert [image.index for image in parse_manifest(manifest_v2).images] == [0, 1]


class TestCollections:
    def test_is_collection(self, collection_v3, manifest_v3):
        assert is_collection(collection_v3)
        assert not is_collection(manifest_v3)

    def test_parse_manifest_rejects_collection(self, collection_v3):
        with pytest.raises(ManifestParseError):
            parse_manifest(collection_v3)

    def test_member_uris_v3(self, collection_v3):
        assert collection_manifest_uris(collection_v3) == [
            "https://example.org/api/iiif/67890/manifest.json",
            "https://example.org/api/iiif/12345/manifest.json",
        ]

    def test_member_uris_v2_merges_manifests_and_collections(self, collection_v2):
        uris = collection_manifest_uris(collection_v2)
        assert "https://example.org/api/iiif/12345/manifest.json" in uris
        assert "https://example.org/api/iiif/collection/top" in uris

    def test_v2_members_takes_precedence(self, collection_v2):
        # Presentation 2.1: a client seeing `members` should use it even when
        # `manifests` / `collections` are also present.
        collection_v2["members"] = [
            {
                "@id": "https://example.org/api/iiif/99999/manifest.json",
                "@type": "sc:Manifest",
                "label": "Ordered member",
            }
        ]
        assert collection_manifest_uris(collection_v2) == [
            "https://example.org/api/iiif/99999/manifest.json"
        ]


class TestLoadManifests:
    def _routes(self, manifest_v2, manifest_v3, collection_v3):
        return {
            "https://example.org/api/iiif/12345/manifest.json": manifest_v2,
            "https://example.org/api/iiif/67890/manifest.json": manifest_v3,
            "https://example.org/api/iiif/collection/top": collection_v3,
        }

    def test_expands_collection(
        self, fake_session_factory, manifest_v2, manifest_v3, collection_v3
    ):
        session = fake_session_factory(self._routes(manifest_v2, manifest_v3, collection_v3))
        manifests = load_manifests(["https://example.org/api/iiif/collection/top"], session=session)
        assert [m.presentation_version for m in manifests] == [3, 2]

    def test_visits_each_uri_once(
        self, fake_session_factory, manifest_v2, manifest_v3, collection_v3
    ):
        session = fake_session_factory(self._routes(manifest_v2, manifest_v3, collection_v3))
        uri = "https://example.org/api/iiif/12345/manifest.json"
        manifests = load_manifests([uri, uri], session=session)
        assert len(manifests) == 1
        assert session.calls.count(uri) == 1

    def test_depth_limit_stops_recursion(
        self, fake_session_factory, manifest_v2, manifest_v3, collection_v3
    ):
        session = fake_session_factory(self._routes(manifest_v2, manifest_v3, collection_v3))
        manifests = load_manifests(
            ["https://example.org/api/iiif/collection/top"], max_depth=0, session=session
        )
        assert manifests == []
