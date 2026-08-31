# Sidebar findings

The official Binary Ninja Python example `hellosidebar.py` shows that a sidebar plugin should import `SidebarWidget`, `SidebarWidgetType`, `Sidebar`, `SidebarWidgetLocation`, and `SidebarContextSensitivity`; subclass `SidebarWidget`; call `SidebarWidget.__init__(self, name)`; implement a `SidebarWidgetType.createWidget(frame, data)` method; define `defaultLocation()`; and register the type with `Sidebar.addSidebarWidgetType(...)`.

The widget receives the active BinaryView as the `data` argument when created for the active view. This is the correct source for the already-open binary, rather than trying to retrieve a BinaryView from a generic PluginCommand context.

Binary Ninja Settings.register_setting requires the properties argument to be a JSON string, not a Python dict. The current plugin already needs this behavior and should retain it.

Sources:
- https://github.com/Vector35/binaryninja-api/blob/dev/python/examples/hellosidebar.py
- https://vector35-binaryninja-api.mintlify.app/plugins/ui-plugins
- https://api.binary.ninja/binaryninja.settings-module.html
