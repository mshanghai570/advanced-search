"""Binary Ninja behavior-category feature search plugin."""
from __future__ import annotations

import threading
from typing import Any

from binaryninja import PluginCommand, Settings, interaction
from .ai import ai_search
from .search import CATEGORIES, search_view

try:
    import binaryninjaui
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                                   QListWidget, QListWidgetItem, QMessageBox, QPushButton, QTableWidget,
                                   QTableWidgetItem, QVBoxLayout)
    UI_AVAILABLE = True
except ImportError:
    UI_AVAILABLE = False

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
        settings.register_setting(f"{SETTINGS_PREFIX}.{suffix}", {"title": title, "type": kind, "default": default, "description": description})
    return settings

SETTINGS = register_settings()

def _settings_value(key: str, default: Any = None) -> Any:
    try:
        value = SETTINGS.get_string(key) if isinstance(default, str) else SETTINGS.get(key)
        return default if value in (None, "") else value
    except Exception:
        return default

if UI_AVAILABLE:
    class FeatureSearchDialog(QDialog):
        search_done = Signal(object, object)
        def __init__(self, bv: Any, parent=None):
            super().__init__(parent)
            self.bv = bv
            self.setWindowTitle("Advanced Search")
            self.resize(900, 600)
            root = QVBoxLayout(self)
            form = QFormLayout()
            self.query = QLineEdit()
            self.query.setPlaceholderText("e.g. payment checkout, credential theft, persistence")
            form.addRow("Search query", self.query)
            self.mode = QComboBox()
            self.mode.addItems(["Local category search", "AI-assisted search"])
            form.addRow("Mode", self.mode)
            root.addLayout(form)
            category_row = QHBoxLayout()
            self.categories = QListWidget()
            self.categories.setSelectionMode(QListWidget.MultiSelection)
            for key, category in CATEGORIES.items():
                item = QListWidgetItem(category.name)
                item.setData(Qt.UserRole, key)
                self.categories.addItem(item)
                item.setSelected(key in ("purchase", "networking", "credential_access"))
            category_row.addWidget(self.categories, 1)
            controls = QVBoxLayout()
            self.search_button = QPushButton("Search")
            self.search_button.clicked.connect(self.run_search)
            controls.addWidget(self.search_button)
            self.status = QLabel("Select categories or use AI mode.")
            self.status.setWordWrap(True)
            controls.addWidget(self.status)
            controls.addStretch(1)
            category_row.addLayout(controls, 1)
            root.addLayout(category_row)
            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(["Category", "Function", "Address", "Score / confidence", "Evidence / rationale"])
            self.table.cellDoubleClicked.connect(self.navigate_to_hit)
            root.addWidget(self.table, 2)
            self.search_done.connect(self.render_results)

        def run_search(self):
            query = self.query.text().strip()
            keys = [item.data(Qt.UserRole) for item in self.categories.selectedItems()]
            self.search_button.setEnabled(False)
            self.status.setText("Searching…")
            if self.mode.currentIndex() == 1:
                threading.Thread(target=self._run_ai, args=(query,), daemon=True).start()
            else:
                threading.Thread(target=self._run_local, args=(keys, query), daemon=True).start()

        def _run_local(self, keys, query):
            try: self.search_done.emit(search_view(self.bv, keys, query), None)
            except Exception as exc: self.search_done.emit([], str(exc))

        def _run_ai(self, query):
            try:
                if not _settings_value(f"{SETTINGS_PREFIX}.ai.enabled", False):
                    raise RuntimeError("AI search is disabled; enable AdvancedSearch.ai.enabled in Settings")
                self.search_done.emit([], ai_search(self.bv, query or "Find behavior matching the selected categories", SETTINGS))
            except Exception as exc: self.search_done.emit([], str(exc))

        def render_results(self, results, error):
            self.search_button.setEnabled(True)
            self.table.setRowCount(0)
            if error:
                self.status.setText("Search failed")
                QMessageBox.critical(self, "Advanced Search", error)
                return
            for result in results:
                row = self.table.rowCount(); self.table.insertRow(row)
                if hasattr(result, "functions"):
                    hit = result.functions[0]; values = [result.category, hit["name"], hex(hit["address"]), str(result.score), ", ".join(result.reasons)]; address = hit["address"]
                else:
                    address = int(result.get("address", 0)); values = [str(result.get("category", "AI match")), str(result.get("name", "")), hex(address), f"{float(result.get('confidence', 0)):.2f}", str(result.get("rationale", ""))]
                self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(address)))
                for col, value in enumerate(values): self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.resizeColumnsToContents(); self.status.setText(f"{len(results)} result(s). Double-click a row to navigate.")

        def navigate_to_hit(self, row, _column):
            try: self.bv.navigate(int(self.table.verticalHeaderItem(row).text(), 0))
            except Exception: pass

_DIALOGS = []
def show_dialog(context):
    if not UI_AVAILABLE:
        interaction.show_message_box("Advanced Search", "UI components are unavailable in headless mode."); return
    bv = getattr(context, "binaryView", None) or getattr(context, "binary_view", None)
    if bv is None:
        interaction.show_message_box("Advanced Search", "Open a binary before starting a search."); return
    dialog = FeatureSearchDialog(bv); _DIALOGS.append(dialog); dialog.show(); dialog.raise_(); dialog.activateWindow()

PluginCommand.register_for_address("Advanced Search\\Search…", "Search functions by behavior category", show_dialog)
PluginCommand.register("Advanced Search\\Search OpenAI-compatible AI…", "AI-assisted behavior search", show_dialog)

__all__ = ["CATEGORIES", "FeatureSearchDialog", "register_settings"]
