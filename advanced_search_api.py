"""Public, dependency-light API for integrations with Advanced Search.

This module intentionally imports no Binary Ninja modules.  The standalone UI
plugin and other plugins can call ``search_binary_view`` with an existing
BinaryView object.
"""

from __future__ import annotations

from typing import Any, Iterable

from search import CATEGORIES, FeatureHit, search_view


def available_categories() -> dict[str, dict[str, str]]:
    """Return the authoritative category keys and metadata."""
    return {
        key: {"name": category.name, "description": category.description}
        for key, category in CATEGORIES.items()
    }


def search_binary_view(
    bv: Any,
    categories: Iterable[str] | None = None,
    query: str = "",
    limit: int = 100,
    include_disassembly: bool = False,
) -> list[FeatureHit]:
    """Run deterministic Advanced Search against an existing BinaryView.

    The function returns the existing ``FeatureHit`` objects rather than a
    second result model, so callers can use all current classification data.
    It never performs network I/O; AI-assisted search remains an explicit UI
    feature implemented by ``ai_search``.
    """
    selected = list(categories or [])
    unknown = [key for key in selected if key not in CATEGORIES]
    if unknown:
        choices = ", ".join(CATEGORIES)
        raise ValueError(f"Unknown Advanced Search category {unknown[0]!r}; choose from: {choices}")
    return search_view(
        bv,
        selected,
        query=query,
        limit=max(1, int(limit)),
        include_disassembly=bool(include_disassembly),
    )


__all__ = ["CATEGORIES", "FeatureHit", "available_categories", "search_binary_view"]
