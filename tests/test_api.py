from __future__ import annotations

from types import SimpleNamespace

from advanced_search_api import available_categories, search_binary_view


def _function(name: str, strings: list[str], address: int):
    return SimpleNamespace(name=name, strings=[SimpleNamespace(value=s) for s in strings], start=address)


def test_categories_are_authoritative():
    categories = available_categories()
    assert "credential_access" in categories
    assert categories["credential_access"]["name"] == "Credential access"


def test_search_binary_view_returns_existing_feature_hits():
    bv = SimpleNamespace(functions=[_function("read_token", ["oauth token"], 0x1234)])
    hits = search_binary_view(bv, ["credential_access"])
    assert hits
    assert hits[0].functions[0] == {"name": "read_token", "address": 0x1234}


def test_unknown_category_fails_without_search():
    try:
        search_binary_view(SimpleNamespace(functions=[]), ["unknown"])
    except ValueError as exc:
        assert "Unknown Advanced Search category" in str(exc)
    else:
        raise AssertionError("unknown categories must be rejected")
