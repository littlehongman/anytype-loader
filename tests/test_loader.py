import json
from pathlib import Path

import pytest

from anytype_loader.loader import AnytypeLoader


# Fixtures
def _load_fixture(name: str) -> dict:
    path = Path("tests/test_files") / name
    return json.loads(path.read_text())


class _DummyResponse:
    def __init__(self, payload: dict):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


# Tests
def test_init_requires_url_and_api_key():
    with pytest.raises(ValueError):
        AnytypeLoader(url="", api_key="", space_names=["personal"])


def test_resolve_space_ids_maps_known_spaces(monkeypatch):
    spaces = [
        {"id": "space-1", "name": "Personal"},
        {"id": "space-2", "name": "Work"},
    ]
    monkeypatch.setattr(AnytypeLoader, "_list_spaces", lambda self: spaces)

    loader = AnytypeLoader(
        url="http://example.com",
        api_key="secret",
        space_names=["Personal", "Work"],
    )

    assert set(loader.space_ids) == {"space-1", "space-2"}
    assert loader.space_name_map == {"space-1": "Personal", "space-2": "Work"}


def test_resolve_space_ids_warns_for_missing_spaces(monkeypatch):
    monkeypatch.setattr(
        AnytypeLoader,
        "_list_spaces",
        lambda self: [{"id": "space-1", "name": "Personal"}],
    )

    with pytest.warns(UserWarning, match="Skipping unknown spaces: Work"):
        loader = AnytypeLoader(
            url="http://example.com",
            api_key="secret",
            space_names=["Personal", "Work"],
        )

    assert set(loader.space_ids) == {"space-1"}


def test_extract_properties_normalizes_and_filters_keys():
    properties = [
        {"key": "tag", "multi_select": [{"name": "alpha"}, {"name": "beta"}]},
        {"key": "created_date", "format": "date", "date": "2024-01-01"},
        {"key": "last_modified_date", "format": "date", "date": "2024-02-02"},
        {"key": "last_opened_date", "format": "date", "date": "2024-03-03"},
        {"key": "description", "format": "text", "text": "hello"},
        {"key": "ignored", "format": "objects", "objects": []},
    ]

    extracted = AnytypeLoader._extract_properties(properties)

    assert extracted == {
        "tags": ["alpha", "beta"],
        "created_at": "2024-01-01",
        "updated_at": "2024-02-02",
        "last_opened_at": "2024-03-03",
        "description": "hello",
    }


def test_parse_objects_response_reads_ids():
    payload = _load_fixture("spaces/space_1.json")
    ids, has_more = AnytypeLoader._parse_objects_response(payload)
    assert len(ids) == 10
    assert ids[0] == "obj-1"
    assert ids[-1] == "obj-10"
    assert has_more is False


def test_iter_object_ids_follows_pagination(monkeypatch):
    monkeypatch.setattr(
        AnytypeLoader, "_list_spaces", lambda self: [{"id": "space-1", "name": "Personal"}]
    )
    pages = [
        (["obj-1", "obj-2"], True),
        (["obj-3"], False),
    ]
    calls = []

    def fake_list_objects(self, space_id, limit, offset):
        calls.append((space_id, limit, offset))
        return pages.pop(0)

    monkeypatch.setattr(AnytypeLoader, "_list_objects", fake_list_objects)

    loader = AnytypeLoader(url="http://example.com", api_key="key", space_names=["Personal"])
    loader.space_ids = ["space-1"]

    result = list(loader._iter_object_ids("space-1"))
    assert result == ["obj-1", "obj-2", "obj-3"]
    assert calls == [("space-1", loader.page_size, 0), ("space-1", loader.page_size, 2)]


def test_fetch_object_returns_markdown_and_metadata(monkeypatch):
    monkeypatch.setattr(
        AnytypeLoader, "_list_spaces", lambda self: [{"id": "space-test", "name": "Personal"}]
    )
    payload = _load_fixture("objects/obj-1.json")

    def fake_request(self, method, url, **kwargs):
        return _DummyResponse(payload)

    monkeypatch.setattr(AnytypeLoader, "_request_with_retries", fake_request)

    loader = AnytypeLoader(url="http://example.com", api_key="key", space_names=["Personal"])
    loader.space_name_map = {"space-test": "Personal"}

    markdown, meta = loader._fetch_object("space-test", "obj-1")

    assert markdown.startswith("# Doc 1")
    expected_meta = {
        "space_id": "space-test",
        "space_name": "Personal",
        "object_id": "obj-1",
        "id": "obj-1",
        "name": "Doc 1 - Availability",
        "archived": False,
        "type": "Page",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "last_opened_at": "2024-01-03T00:00:00Z",
        "tags": ["alpha"],
        "description": "Desc 1",
    }
    assert meta == expected_meta
