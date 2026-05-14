# Copyright (c) 2025 Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

from rv import commands, rvtypes, qtutils

try:
    from PySide2 import QtCore, QtWidgets, QtGui
except ImportError:
    from PySide6 import QtCore, QtWidgets, QtGui

from annotate_toolbar_widget import (
    AnnotateToolbarDockWidget,
    TOOL_PEN,
)
from annotate_toolbar_engine import AnnotateDrawEngine, TABLE_NAME, _DRAWING_TOOLS


class AnnotateToolbarMode(rvtypes.MinorMode):
    def __init__(self):
        rvtypes.MinorMode.__init__(self)

        self._dock = None
        self._shape_table_pushed = False

        # Current tool state — drawing engine reads these
        self._tool = TOOL_PEN
        self._colour = QtGui.QColor(255, 220, 0)
        self._size = 32
        self._opacity = 50
        self._filled = False
        self._font_family = "Helvetica"
        self._font_size = "medium"
        self._font_bold = False
        self._font_italic = False
        self._font_underline = False

        self._engine = AnnotateDrawEngine(self)

        self.init(
            "annotate_toolbar_mode",
            self.global_bindings,
            [],  # no global pointer bindings — only the named table below
            self.menu,
        )

        # Register the named event table AFTER init() so mode name is set.
        # This table is pushed on top of Mu's "draw" table only when a shape
        # tool is active, giving us higher priority than Mu's always-pushed table.
        self._engine.setup_event_table(self)

        self._create_dock()

    # ------------------------------------------------------------------
    # MinorMode interface
    # ------------------------------------------------------------------

    def activate(self):
        rvtypes.MinorMode.activate(self)
        self._dock.show()

    def deactivate(self):
        self._pop_shape_table()
        self._dock.hide()
        rvtypes.MinorMode.deactivate(self)

    # ------------------------------------------------------------------
    # Event table push / pop
    # ------------------------------------------------------------------

    def _push_shape_table(self):
        if not self._shape_table_pushed:
            commands.pushEventTable(TABLE_NAME)
            self._shape_table_pushed = True

    def _pop_shape_table(self):
        if self._shape_table_pushed:
            commands.popEventTable()
            self._shape_table_pushed = False

    # ------------------------------------------------------------------
    # Dock creation
    # ------------------------------------------------------------------

    def _create_dock(self):
        sw = qtutils.sessionWindow()
        self._dock = AnnotateToolbarDockWidget(sw)
        sw.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self._dock)
        sw.resizeDocks([self._dock], [200], QtCore.Qt.Horizontal)

        for existing in sw.findChildren(QtWidgets.QDockWidget):
            if existing is self._dock:
                continue
            if sw.dockWidgetArea(existing) == QtCore.Qt.LeftDockWidgetArea:
                sw.tabifyDockWidget(existing, self._dock)
                break

        w = self._dock.toolbar_widget
        w.tool_changed.connect(self._on_tool_changed)
        w.colour_changed.connect(self._on_colour_changed)
        w.size_changed.connect(self._on_size_changed)
        w.opacity_changed.connect(self._on_opacity_changed)
        w.filled_changed.connect(self._on_filled_changed)
        w.font_family_changed.connect(self._on_font_family_changed)
        w.font_size_changed.connect(self._on_font_size_changed)
        w.font_bold_changed.connect(self._on_font_bold_changed)
        w.font_italic_changed.connect(self._on_font_italic_changed)
        w.font_underline_changed.connect(self._on_font_underline_changed)
        w.undo_requested.connect(self._on_undo)
        w.redo_requested.connect(self._on_redo)
        w.clear_requested.connect(self._on_clear)

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_tool_changed(self, tool):
        self._tool = tool
        if tool in _DRAWING_TOOLS:
            self._push_shape_table()
        else:
            self._engine.commit_text_if_active()
            self._pop_shape_table()

    def _on_colour_changed(self, colour):
        self._colour = colour

    def _on_size_changed(self, v):
        self._size = v

    def _on_opacity_changed(self, v):
        self._opacity = v

    def _on_filled_changed(self, v):
        self._filled = v

    def _on_font_family_changed(self, v):
        self._font_family = v
        self._engine.update_text_style()

    def _on_font_size_changed(self, v):
        self._font_size = v
        self._engine.update_text_style()

    def _on_font_bold_changed(self, v):
        self._font_bold = v
        self._engine.update_text_style()

    def _on_font_italic_changed(self, v):
        self._font_italic = v
        self._engine.update_text_style()

    def _on_font_underline_changed(self, v):
        self._font_underline = v
        self._engine.update_text_style()

    def _on_undo(self):
        pass  # Phase 5

    def _on_redo(self):
        pass  # Phase 5

    def _on_clear(self):
        pass  # Phase 5

    # ------------------------------------------------------------------
    # Bindings and menu
    # ------------------------------------------------------------------

    @property
    def global_bindings(self):
        return []

    @property
    def menu(self):
        return [
            (
                "Annotation",
                [
                    (
                        "New Toolbar (Preview)",
                        lambda e: commands.sendInternalEvent("mode-manager-toggle-mode", "annotate_toolbar_mode"),
                        None,
                        lambda: commands.NeutralMenuState,
                    )
                ],
            )
        ]


def createMode():
    return AnnotateToolbarMode()
