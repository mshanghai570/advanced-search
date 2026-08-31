import importlib.util
import sys
import types

class FakeSettings:
    schemas = []
    def __init__(self): self.values = {}
    def register_group(self, key, title): return True
    def register_setting(self, key, properties):
        assert isinstance(properties, str), (key, type(properties))
        self.schemas.append((key, properties))
        return True
    def get(self, key): return False
    def get_string(self, key): return ""

class FakePluginCommand:
    @staticmethod
    def register(*args): return True
    @staticmethod
    def register_for_address(*args): return True

binaryninja = types.ModuleType("binaryninja")
binaryninja.Settings = FakeSettings
binaryninja.PluginCommand = FakePluginCommand
binaryninja.interaction = types.SimpleNamespace(show_message_box=lambda *args: None)
sys.modules["binaryninja"] = binaryninja
sys.modules["binaryninjaui"] = types.ModuleType("binaryninjaui")

spec = importlib.util.spec_from_file_location("advanced_search", "__init__.py", submodule_search_locations=["."])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
assert len(FakeSettings.schemas) == 6
print("initializer settings test passed")
