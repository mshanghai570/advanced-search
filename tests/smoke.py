import importlib.util
import sys
from types import SimpleNamespace

# Load search.py directly so the test does not need Binary Ninja installed.
spec = importlib.util.spec_from_file_location("bn_feature_search.search", "bn_feature_search/search.py")
search = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = search
spec.loader.exec_module(search)

def fn(name, strings, address):
    return SimpleNamespace(name=name, start=address, strings=[SimpleNamespace(value=s) for s in strings], basic_blocks=[])

bv = SimpleNamespace(functions=[fn("checkout_order", ["https://shop.example/checkout", "payment"], 0x1000), fn("local", ["read file"], 0x2000)])
hits = search.search_view(bv, ["purchase"], "")
assert hits and hits[0].functions[0]["address"] == 0x1000
debug_hits = search.search_view(bv, ["purchase", "file_activity"], "shop.example")
assert {hit.category for hit in debug_hits} == {"Purchase / commerce", "File activity"}
print("smoke tests passed")
