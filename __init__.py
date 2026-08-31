"""Advanced Search: Binary Ninja behavior-category sidebar plugin."""
from __future__ import annotations

import json
import threading
from typing import Any

from binaryninja import PluginCommand, Settings, interaction

SETTINGS_PREFIX = "AdvancedSearch"


def register_settings() -> Settings:
    settings = Settings()
    settings.register_group(SETTINGS_PREFIX, "Advanced Search")
    specs = {
        "ai.enabled": ("Enable AI search", "boolean", False, "Allow sending a compact function summary to a provider."),
        "ai.base_url": ("OpenAI-compatible base URL", "string", "https://api.openai.com/v1", "Provider root URL; /chat/completions is appended."),
        "ai.api_key": ("API key", "string", "", "Provider API key."),
        "ai.model": ("Model", "string", "gpt-4o-mini", "Model identifier accepted by your provider."),
        "ai.timeout_seconds": ("Request timeout", "number", 30, "AI request timeout in seconds."),
        "ai.max_functions": ("Maximum functions sent", "number", 250, "Caps the local function summary sent to the provider."),
    }
    for suffix, (title, kind, default, description) in specs.items():
        properties = {"title": title, "type": kind, "default": default, "description": description,
                      "ignore": ["SettingsProjectScope", "SettingsResourceScope"]}
        settings.register_setting(f"{SETTINGS_PREFIX}.{suffix}", json.dumps(properties))
    return settings


SETTINGS = register_settings()


def _settings_value(key: str, default: Any = None) -> Any:
    try:
        value = SETTINGS.get_string(key) if isinstance(default, str) else SETTINGS.get(key)
        return default if value in (None, "") else value
    except Exception:
        return default


try:
    import binaryninjaui
    from binaryninjaui import (Sidebar, SidebarContextSensitivity, SidebarWidget,
                               SidebarWidgetLocation, SidebarWidgetType)
    from PySide6.QtCore import QRectF, Qt, Signal
    from PySide6.QtGui import QColor, QFont, QImage, QPainter
    from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                                   QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem,
                                   QVBoxLayout)
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False


if UI_AVAILABLE:
    from .ai import ai_search
    from .search import CATEGORIES, search_view

    class AdvancedSearchSidebarWidget(SidebarWidget):
        results_ready = Signal(object, object)

        def __init__(self, name: str, frame: Any, data: Any):
            SidebarWidget.__init__(self, name)
            self.frame = frame
            self.data = data
            self._build_ui()
            self.results_ready.connect(self._render_results)

        def _build_ui(self):
            layout = QVBoxLayout()
            layout.setContentsMargins(8, 8, 8, 8)
            title = QLabel("Advanced Search")
            title.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(title)
            self.binary_label = QLabel(self._binary_name())
            self.binary_label.setToolTip("BinaryView supplied by the active Binary Ninja view")
            layout.addWidget(self.binary_label)
            self.query = QLineEdit()
            self.query.setPlaceholderText("e.g. purchase, credential theft, persistence")
            self.query.returnPressed.connect(self.run_search)
            layout.addWidget(self.query)
            self.mode = QComboBox()
            self.mode.addItems(["Local category search", "AI-assisted search"])
            layout.addWidget(self.mode)
            self.categories = QListWidget()
            self.categories.setSelectionMode(QListWidget.MultiSelection)
            for key, category in CATEGORIES.items():
                item = QListWidgetItem(category.name)
                item.setData(Qt.UserRole, key)
                self.categories.addItem(item)
                item.setSelected(key in ("purchase", "networking", "credential_access"))
            layout.addWidget(self.categories, 1)
            self.search_button = QPushButton("Search active binary")
            self.search_button.clicked.connect(self.run_search)
            layout.addWidget(self.search_button)
            self.status = QLabel("This panel is attached to the currently open BinaryView.")
            self.status.setWordWrap(True)
            layout.addWidget(self.status)
            self.table = QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Category", "Function", "Address", "Evidence / rationale"])
            self.table.cellDoubleClicked.connect(self.navigate_to_hit)
            layout.addWidget(self.table, 2)
            self.setLayout(layout)

        def _binary_name(self) -> str:
            try:
                return str(self.data.file.filename)
            except Exception:
                return "Active BinaryView"

        def notifyViewChanged(self, view_frame):
            if view_frame is not None:
                try:
                    self.data = view_frame.getCurrentViewInterface().getData()
                    self.binary_label.setText(self._binary_name())
                except Exception:
                    pass

        def run_search(self):
            if self.data is None:
                self.status.setText("No BinaryView is currently active.")
                return
            query = self.query.text().strip()
            keys = [item.data(Qt.UserRole) for item in self.categories.selectedItems()]
            self.search_button.setEnabled(False)
            self.status.setText("Searching active binary…")
            if self.mode.currentIndex() == 1:
                threading.Thread(target=self._run_ai, args=(query,), daemon=True).start()
            else:
                threading.Thread(target=self._run_local, args=(keys, query), daemon=True).start()

        def _run_local(self, keys, query):
            try:
                self.results_ready.emit(search_view(self.data, keys, query), None)
            except Exception as exc:
                self.results_ready.emit([], str(exc))

        def _run_ai(self, query):
            try:
                if not _settings_value(f"{SETTINGS_PREFIX}.ai.enabled", False):
                    raise RuntimeError("AI search is disabled; enable AdvancedSearch.ai.enabled in Settings")
                self.results_ready.emit([], ai_search(self.data, query or "Find behavior matching the selected categories", SETTINGS))
            except Exception as exc:
                self.results_ready.emit([], str(exc))

        def _render_results(self, results, error):
            self.search_button.setEnabled(True)
            self.table.setRowCount(0)
            if error:
                self.status.setText(f"Search failed: {error}")
                return
            for result in results:
                row = self.table.rowCount()
                self.table.insertRow(row)
                if hasattr(result, "functions"):
                    hit = result.functions[0]
                    values = [result.category, hit["name"], hex(hit["address"]), ", ".join(result.reasons)]
                    address = hit["address"]
                else:
                    address = int(result.get("address", 0))
                    values = [str(result.get("category", "AI match")), str(result.get("name", "")), hex(address), str(result.get("rationale", ""))]
                self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(address)))
                for column, value in enumerate(values):
                    self.table.setItem(row, column, QTableWidgetItem(value))
            self.table.resizeColumnsToContents()
            self.status.setText(f"{len(results)} result(s). Double-click a row to navigate.")

        def navigate_to_hit(self, row, _column):
            try:
                self.data.navigate(int(self.table.verticalHeaderItem(row).text(), 0))
            except Exception:
                pass

        def contextMenuEvent(self, event):
            try:
                self.m_contextMenuManager.show(self.m_menu, self.actionHandler)
            except Exception:
                super().contextMenuEvent(event)


    class AdvancedSearchSidebarWidgetType(SidebarWidgetType):
        def __init__(self):
            icon = QImage(56, 56, QImage.Format_RGB32)
            icon.fill(0)
            painter = QPainter(icon)
            painter.setFont(QFont("Open Sans", 44))
            painter.setPen(QColor(255, 255, 255, 255))
            painter.drawText(QRectF(0, 0, 56, 56), Qt.AlignCenter, "A")
            painter.end()
            SidebarWidgetType.__init__(self, icon, "Advanced Search")

        def createWidget(self, frame, data):
            return AdvancedSearchSidebarWidget("Advanced Search", frame, data)

        def defaultLocation(self):
            return SidebarWidgetLocation.RightContent

        def contextSensitivity(self):
            return SidebarContextSensitivity.SelfManagedSidebarContext


    SIDEBAR_TYPE = AdvancedSearchSidebarWidgetType()
    Sidebar.addSidebarWidgetType(SIDEBAR_TYPE)


def show_sidebar_hint(context):
    interaction.show_message_box("Advanced Search", "Use the Advanced Search icon in the Binary Ninja sidebar. It is attached to the active BinaryView.")


PluginCommand.register("Advanced Search\\Open Sidebar", "Open the Advanced Search sidebar panel", show_sidebar_hint)

__all__ = ["register_settings"]
if UI_AVAILABLE:
    __all__ += ["AdvancedSearchSidebarWidget", "AdvancedSearchSidebarWidgetType"]
