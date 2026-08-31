import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
from search import CATEGORIES, search_view


def function(name, strings, address):
    return SimpleNamespace(name=name, start=address, strings=[SimpleNamespace(value=s) for s in strings], basic_blocks=[])


def test_purchase_category():
    bv = SimpleNamespace(functions=[function("checkout_order", ["https://shop.example/checkout", "payment"], 0x1000)])
    hits = search_view(bv, ["purchase"])
    assert hits and hits[0].category == CATEGORIES["purchase"].name
    assert hits[0].functions[0]["address"] == 0x1000


def test_query_filters_results():
    bv = SimpleNamespace(functions=[function("network", ["https://example.com"], 0x1000), function("local", ["read file"], 0x2000)])
    hits = search_view(bv, ["networking", "file_activity"], "example.com")
    assert len(hits) == 1 and hits[0].functions[0]["address"] == 0x1000
