import pytest

from anytype_loader.loader import AnytypeLoader


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
