# Copyright (c) 2025 Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

try:
    from PySide2 import QtCore, QtWidgets, QtGui
except ImportError:
    from PySide6 import QtCore, QtWidgets, QtGui

from annotate_toolbar_colour_picker import ColourPickerPopup

# Tool identifiers
TOOL_CURSOR = "cursor"
TOOL_PEN = "pen"
TOOL_AIRBRUSH = "airbrush"
TOOL_ERASER = "eraser"
TOOL_LASER = "laser"
TOOL_RECT = "rect"
TOOL_CIRCLE = "circle"
TOOL_ARROW = "arrow"
TOOL_LINE = "line"
TOOL_TEXT = "text"

# Secondary panel page indices
_PAGE_EMPTY = 0  # cursor, laser
_PAGE_BRUSH = 1  # pen, airbrush, eraser, arrow, line
_PAGE_SHAPE = 2  # rect, circle
_PAGE_TEXT = 3  # text

_TOOL_PAGE = {
    TOOL_CURSOR: _PAGE_EMPTY,
    TOOL_LASER: _PAGE_EMPTY,
    TOOL_PEN: _PAGE_BRUSH,
    TOOL_AIRBRUSH: _PAGE_BRUSH,
    TOOL_ERASER: _PAGE_BRUSH,
    TOOL_ARROW: _PAGE_BRUSH,
    TOOL_LINE: _PAGE_BRUSH,
    TOOL_RECT: _PAGE_SHAPE,
    TOOL_CIRCLE: _PAGE_SHAPE,
    TOOL_TEXT: _PAGE_TEXT,
}

# TODO: replace with SVG icons loaded from annotation-platform assets
_TOOL_LABEL = {
    TOOL_CURSOR: "↖",
    TOOL_PEN: "✏",
    TOOL_AIRBRUSH: "≈",
    TOOL_ERASER: "⌫",
    TOOL_LASER: "✦",
    TOOL_RECT: "▭",
    TOOL_CIRCLE: "○",
    TOOL_ARROW: "↗",
    TOOL_LINE: "╱",
    TOOL_TEXT: "T",
}

_TOOL_TOOLTIP = {
    TOOL_CURSOR: "Cursor",
    TOOL_PEN: "Pen",
    TOOL_AIRBRUSH: "Airbrush",
    TOOL_ERASER: "Eraser",
    TOOL_LASER: "Laser Pointer",
    TOOL_RECT: "Rectangle",
    TOOL_CIRCLE: "Circle",
    TOOL_ARROW: "Arrow",
    TOOL_LINE: "Line",
    TOOL_TEXT: "Text",
}

_FONT_SIZES = ("small", "medium", "large")
_FONT_SIZE_LABELS = {"small": "S", "medium": "M", "large": "L"}

# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

_STRIP_SS = """
    QWidget#AnnotateToolStrip {
        background: #1a1a1a;
    }
    QToolButton {
        background: transparent;
        border: none;
        color: #c8c8c8;
        font-size: 14px;
        border-radius: 4px;
        padding: 0px;
    }
    QToolButton:hover  { background: #2d2d2d; }
    QToolButton:checked { background: #3d7ebf; }
    QToolButton:disabled { color: #505050; }
"""

_PANEL_SS = """
    QWidget#AnnotateSecondaryPanel, QWidget#AnnotateSecondaryPanel * {
        background: #1a1a1a;
    }
    QLabel {
        color: #707070;
        font-size: 10px;
        background: transparent;
    }
    QCheckBox {
        color: #c8c8c8;
        font-size: 10px;
    }
    QCheckBox::indicator {
        width: 12px;
        height: 12px;
        border: 1px solid #555555;
        border-radius: 2px;
        background: transparent;
    }
    QCheckBox::indicator:checked {
        background: #3d7ebf;
        border-color: #3d7ebf;
    }
    QToolButton {
        background: transparent;
        border: 1px solid #404040;
        color: #c8c8c8;
        font-size: 11px;
        border-radius: 3px;
        padding: 1px 4px;
        min-width: 18px;
        min-height: 18px;
    }
    QToolButton:hover   { background: #2d2d2d; }
    QToolButton:checked { background: #3d7ebf; border-color: #3d7ebf; }
    QComboBox {
        background: #2a2a2a;
        border: 1px solid #404040;
        color: #c8c8c8;
        font-size: 10px;
        padding: 2px 4px;
        border-radius: 3px;
    }
    QComboBox::drop-down { border: none; }
    QSlider::groove:vertical {
        background: #3a3a3a;
        width: 4px;
        border-radius: 2px;
    }
    QSlider::handle:vertical {
        background: #4fa3e0;
        width: 12px; height: 12px;
        margin: -4px -4px;
        border-radius: 6px;
    }
    QSlider::sub-page:vertical {
        background: #4fa3e0;
        border-radius: 2px;
    }
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tool_button(label, tooltip, checkable=True, size=30):
    btn = QtWidgets.QToolButton()
    btn.setText(label)
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    btn.setFixedSize(size, size)
    return btn


def _separator(horizontal=True):
    sep = QtWidgets.QFrame()
    sep.setFrameShape(QtWidgets.QFrame.HLine if horizontal else QtWidgets.QFrame.VLine)
    sep.setStyleSheet("QFrame { background: #333333; border: none; max-height: 1px; }")
    return sep


# ---------------------------------------------------------------------------
# Colour swatch
# ---------------------------------------------------------------------------


class ColourSwatch(QtWidgets.QAbstractButton):
    """Circular button showing the current annotation colour.

    Clicking it opens the ColourPickerPopup.
    """

    colour_changed = QtCore.Signal(QtGui.QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colour = QtGui.QColor(255, 220, 0)
        self._popup = ColourPickerPopup()
        self._popup.colour_changed.connect(self._on_popup_colour)
        self.setFixedSize(30, 30)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setToolTip("Colour")

    def get_colour(self):
        return QtGui.QColor(self._colour)

    def set_colour(self, colour):
        self._colour = QtGui.QColor(colour)
        self.update()

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing, True)

        # Outer ring painted as a small rainbow to indicate "colour picker"
        ring_rect = self.rect().adjusted(2, 2, -2, -2)
        grad = QtGui.QConicalGradient(ring_rect.center(), 0)
        for i in range(7):
            grad.setColorAt(i / 6.0, QtGui.QColor.fromHsvF(i / 6.0, 1.0, 1.0))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(ring_rect)

        # Inner circle filled with current colour
        inner = self.rect().adjusted(5, 5, -5, -5)
        p.setBrush(self._colour)
        p.setPen(QtGui.QPen(QtGui.QColor("#1a1a1a"), 1))
        p.drawEllipse(inner)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._popup.set_colour(self._colour)
            pos = self.mapToGlobal(QtCore.QPoint(self.width() + 4, 0))
            self._popup.show_at(pos)

    def _on_popup_colour(self, colour):
        self._colour = colour
        self.update()
        self.colour_changed.emit(colour)


# ---------------------------------------------------------------------------
# Secondary panel option pages
# ---------------------------------------------------------------------------


class _SliderSection(QtWidgets.QWidget):
    """Label + vertical slider + numeric value readout."""

    value_changed = QtCore.Signal(int)

    def __init__(self, label, min_val, max_val, default, suffix="", parent=None):
        super().__init__(parent)
        self._suffix = suffix

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        lbl = QtWidgets.QLabel(label)
        lbl.setAlignment(QtCore.Qt.AlignHCenter)
        lay.addWidget(lbl)

        self._slider = QtWidgets.QSlider(QtCore.Qt.Vertical)
        self._slider.setRange(min_val, max_val)
        self._slider.setValue(default)
        self._slider.setMinimumHeight(90)
        lay.addWidget(self._slider, alignment=QtCore.Qt.AlignHCenter)
        self._slider.valueChanged.connect(self._on_value)

        self._val_lbl = QtWidgets.QLabel(f"{default}{suffix}")
        self._val_lbl.setAlignment(QtCore.Qt.AlignHCenter)
        lay.addWidget(self._val_lbl)

    def get_value(self):
        return self._slider.value()

    def set_value(self, v):
        self._slider.setValue(v)

    def _on_value(self, v):
        self._val_lbl.setText(f"{v}{self._suffix}")
        self.value_changed.emit(v)


class _SizeOpacityPanel(QtWidgets.QWidget):
    size_changed = QtCore.Signal(int)
    opacity_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(12)

        self._size = _SliderSection("Size", 1, 200, 32)
        self._size.value_changed.connect(self.size_changed)
        lay.addWidget(self._size)

        self._opacity = _SliderSection("Opacity", 0, 100, 50, suffix="%")
        self._opacity.value_changed.connect(self.opacity_changed)
        lay.addWidget(self._opacity)

        lay.addStretch()

    def get_size(self):
        return self._size.get_value()

    def get_opacity(self):
        return self._opacity.get_value()

    def set_size(self, v):
        self._size.set_value(v)

    def set_opacity(self, v):
        self._opacity.set_value(v)


class _ShapeOptionsPanel(QtWidgets.QWidget):
    filled_changed = QtCore.Signal(bool)
    size_changed = QtCore.Signal(int)
    opacity_changed = QtCore.Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(12)

        self._filled = QtWidgets.QCheckBox("Filled")
        self._filled.setChecked(False)
        self._filled.toggled.connect(self.filled_changed)
        lay.addWidget(self._filled)

        self._size = _SliderSection("Size", 1, 200, 32)
        self._size.value_changed.connect(self.size_changed)
        lay.addWidget(self._size)

        self._opacity = _SliderSection("Opacity", 0, 100, 50, suffix="%")
        self._opacity.value_changed.connect(self.opacity_changed)
        lay.addWidget(self._opacity)

        lay.addStretch()

    def get_filled(self):
        return self._filled.isChecked()

    def get_size(self):
        return self._size.get_value()

    def get_opacity(self):
        return self._opacity.get_value()

    def set_filled(self, v):
        self._filled.setChecked(v)

    def set_size(self, v):
        self._size.set_value(v)

    def set_opacity(self, v):
        self._opacity.set_value(v)


class _TextOptionsPanel(QtWidgets.QWidget):
    font_family_changed = QtCore.Signal(str)
    font_size_changed = QtCore.Signal(str)  # "small" | "medium" | "large"
    font_bold_changed = QtCore.Signal(bool)
    font_italic_changed = QtCore.Signal(bool)
    font_underline_changed = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Font family
        # TODO: replace with fonts bundled in annotation-platform once available
        self._font_combo = QtWidgets.QComboBox()
        for name in ("Helvetica", "Courier", "Marker Felt"):
            self._font_combo.addItem(name)
        self._font_combo.currentTextChanged.connect(self.font_family_changed)
        lay.addWidget(self._font_combo)

        # S / M / L size buttons
        size_row = QtWidgets.QWidget()
        size_lay = QtWidgets.QHBoxLayout(size_row)
        size_lay.setContentsMargins(0, 0, 0, 0)
        size_lay.setSpacing(3)
        self._size_btns = {}
        self._size_grp = QtWidgets.QButtonGroup(self)
        for key in _FONT_SIZES:
            btn = QtWidgets.QToolButton()
            btn.setText(_FONT_SIZE_LABELS[key])
            btn.setCheckable(True)
            btn.setToolTip(key.capitalize())
            self._size_btns[key] = btn
            self._size_grp.addButton(btn)
            size_lay.addWidget(btn)
        self._size_btns["medium"].setChecked(True)
        self._size_grp.buttonClicked.connect(self._on_size_btn)
        lay.addWidget(size_row)

        # B / I / U style toggles
        style_row = QtWidgets.QWidget()
        style_lay = QtWidgets.QHBoxLayout(style_row)
        style_lay.setContentsMargins(0, 0, 0, 0)
        style_lay.setSpacing(3)

        self._bold_btn = QtWidgets.QToolButton()
        self._bold_btn.setText("B")
        self._bold_btn.setCheckable(True)
        self._bold_btn.setToolTip("Bold")
        font_b = self._bold_btn.font()
        font_b.setBold(True)
        self._bold_btn.setFont(font_b)
        self._bold_btn.toggled.connect(self.font_bold_changed)
        style_lay.addWidget(self._bold_btn)

        self._italic_btn = QtWidgets.QToolButton()
        self._italic_btn.setText("I")
        self._italic_btn.setCheckable(True)
        self._italic_btn.setToolTip("Italic")
        font_i = self._italic_btn.font()
        font_i.setItalic(True)
        self._italic_btn.setFont(font_i)
        self._italic_btn.toggled.connect(self.font_italic_changed)
        style_lay.addWidget(self._italic_btn)

        self._underline_btn = QtWidgets.QToolButton()
        self._underline_btn.setText("U")
        self._underline_btn.setCheckable(True)
        self._underline_btn.setToolTip("Underline")
        font_u = self._underline_btn.font()
        font_u.setUnderline(True)
        self._underline_btn.setFont(font_u)
        self._underline_btn.toggled.connect(self.font_underline_changed)
        style_lay.addWidget(self._underline_btn)

        style_lay.addStretch()
        lay.addWidget(style_row)
        lay.addStretch()

    def _on_size_btn(self, btn):
        for key, b in self._size_btns.items():
            if b is btn:
                self.font_size_changed.emit(key)
                return

    def get_font_family(self):
        return self._font_combo.currentText()

    def get_font_size(self):
        for key, btn in self._size_btns.items():
            if btn.isChecked():
                return key
        return "medium"

    def get_bold(self):
        return self._bold_btn.isChecked()

    def get_italic(self):
        return self._italic_btn.isChecked()

    def get_underline(self):
        return self._underline_btn.isChecked()


# ---------------------------------------------------------------------------
# Secondary panel
# ---------------------------------------------------------------------------


class AnnotateSecondaryPanel(QtWidgets.QWidget):
    colour_changed = QtCore.Signal(QtGui.QColor)
    size_changed = QtCore.Signal(int)
    opacity_changed = QtCore.Signal(int)
    filled_changed = QtCore.Signal(bool)
    font_family_changed = QtCore.Signal(str)
    font_size_changed = QtCore.Signal(str)
    font_bold_changed = QtCore.Signal(bool)
    font_italic_changed = QtCore.Signal(bool)
    font_underline_changed = QtCore.Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotateSecondaryPanel")
        self.setMinimumWidth(64)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 8, 4, 8)
        lay.setSpacing(6)

        self._swatch = ColourSwatch()
        self._swatch.colour_changed.connect(self.colour_changed)
        lay.addWidget(self._swatch, alignment=QtCore.Qt.AlignHCenter)

        lay.addWidget(_separator(horizontal=True))

        self._stack = QtWidgets.QStackedWidget()
        lay.addWidget(self._stack)

        # Page 0 — empty (cursor / laser)
        self._stack.addWidget(QtWidgets.QWidget())

        # Page 1 — brush tools (pen, airbrush, eraser, arrow, line)
        self._brush_panel = _SizeOpacityPanel()
        self._brush_panel.size_changed.connect(self.size_changed)
        self._brush_panel.opacity_changed.connect(self.opacity_changed)
        self._stack.addWidget(self._brush_panel)

        # Page 2 — shape tools (rect, circle)
        self._shape_panel = _ShapeOptionsPanel()
        self._shape_panel.filled_changed.connect(self.filled_changed)
        self._shape_panel.size_changed.connect(self.size_changed)
        self._shape_panel.opacity_changed.connect(self.opacity_changed)
        self._stack.addWidget(self._shape_panel)

        # Page 3 — text tool
        self._text_panel = _TextOptionsPanel()
        self._text_panel.font_family_changed.connect(self.font_family_changed)
        self._text_panel.font_size_changed.connect(self.font_size_changed)
        self._text_panel.font_bold_changed.connect(self.font_bold_changed)
        self._text_panel.font_italic_changed.connect(self.font_italic_changed)
        self._text_panel.font_underline_changed.connect(self.font_underline_changed)
        self._stack.addWidget(self._text_panel)

    def set_page_for_tool(self, tool):
        self._stack.setCurrentIndex(_TOOL_PAGE.get(tool, _PAGE_EMPTY))

    # Passthrough accessors for the mode to read current state
    def get_colour(self):
        return self._swatch.get_colour()

    def set_colour(self, c):
        self._swatch.set_colour(c)

    def get_size(self):
        p = self._stack.currentIndex()
        if p == _PAGE_BRUSH:
            return self._brush_panel.get_size()
        if p == _PAGE_SHAPE:
            return self._shape_panel.get_size()
        return 32

    def get_opacity(self):
        p = self._stack.currentIndex()
        if p == _PAGE_BRUSH:
            return self._brush_panel.get_opacity()
        if p == _PAGE_SHAPE:
            return self._shape_panel.get_opacity()
        return 50

    def get_filled(self):
        return self._shape_panel.get_filled()

    def get_font_family(self):
        return self._text_panel.get_font_family()

    def get_font_size(self):
        return self._text_panel.get_font_size()

    def get_bold(self):
        return self._text_panel.get_bold()

    def get_italic(self):
        return self._text_panel.get_italic()

    def get_underline(self):
        return self._text_panel.get_underline()


# ---------------------------------------------------------------------------
# Tool strip
# ---------------------------------------------------------------------------


class AnnotateToolStrip(QtWidgets.QWidget):
    """Narrow vertical column of annotation tool buttons."""

    tool_changed = QtCore.Signal(str)
    undo_requested = QtCore.Signal()
    redo_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnnotateToolStrip")
        self.setFixedWidth(30)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(0)

        self._group = QtWidgets.QButtonGroup(self)
        self._buttons = {}

        def _add_tool(tool):
            btn = _tool_button(_TOOL_LABEL[tool], _TOOL_TOOLTIP[tool])
            self._buttons[tool] = btn
            self._group.addButton(btn)
            lay.addWidget(btn)

        _add_tool(TOOL_CURSOR)
        lay.addSpacing(2)

        lay.addWidget(_separator())
        lay.addSpacing(2)

        for tool in (TOOL_PEN, TOOL_AIRBRUSH, TOOL_ERASER, TOOL_LASER):
            _add_tool(tool)

        lay.addSpacing(2)
        lay.addWidget(_separator())
        lay.addSpacing(2)

        for tool in (TOOL_RECT, TOOL_CIRCLE, TOOL_ARROW, TOOL_LINE, TOOL_TEXT):
            _add_tool(tool)

        lay.addStretch()

        lay.addWidget(_separator())
        lay.addSpacing(2)

        self._undo_btn = _tool_button("↩", "Undo", checkable=False)
        self._undo_btn.setEnabled(False)
        self._undo_btn.clicked.connect(self.undo_requested)
        lay.addWidget(self._undo_btn)

        self._redo_btn = _tool_button("↪", "Redo", checkable=False)
        self._redo_btn.setEnabled(False)
        self._redo_btn.clicked.connect(self.redo_requested)
        lay.addWidget(self._redo_btn)

        self._clear_btn = _tool_button("⊗", "Clear Frame", checkable=False)
        self._clear_btn.clicked.connect(self.clear_requested)
        lay.addWidget(self._clear_btn)

        self._group.buttonClicked.connect(self._on_tool_clicked)
        self._buttons[TOOL_PEN].setChecked(True)

    def _on_tool_clicked(self, btn):
        for tool, b in self._buttons.items():
            if b is btn:
                self.tool_changed.emit(tool)
                return

    def set_active_tool(self, tool):
        btn = self._buttons.get(tool)
        if btn:
            btn.setChecked(True)

    def set_undo_enabled(self, enabled):
        self._undo_btn.setEnabled(enabled)

    def set_redo_enabled(self, enabled):
        self._redo_btn.setEnabled(enabled)


# ---------------------------------------------------------------------------
# Top-level widget and dock
# ---------------------------------------------------------------------------


class AnnotateToolbarWidget(QtWidgets.QWidget):
    """Combined strip + secondary panel.  All signals bubble up from children."""

    tool_changed = QtCore.Signal(str)
    colour_changed = QtCore.Signal(QtGui.QColor)
    size_changed = QtCore.Signal(int)
    opacity_changed = QtCore.Signal(int)
    filled_changed = QtCore.Signal(bool)
    font_family_changed = QtCore.Signal(str)
    font_size_changed = QtCore.Signal(str)
    font_bold_changed = QtCore.Signal(bool)
    font_italic_changed = QtCore.Signal(bool)
    font_underline_changed = QtCore.Signal(bool)
    undo_requested = QtCore.Signal()
    redo_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_STRIP_SS + _PANEL_SS)

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._strip = AnnotateToolStrip()
        lay.addWidget(self._strip)

        self._panel = AnnotateSecondaryPanel()
        lay.addWidget(self._panel)

        # Wire strip → panel page switch and bubble signals up
        self._strip.tool_changed.connect(self._on_tool_changed)
        self._strip.undo_requested.connect(self.undo_requested)
        self._strip.redo_requested.connect(self.redo_requested)
        self._strip.clear_requested.connect(self.clear_requested)

        self._panel.colour_changed.connect(self.colour_changed)
        self._panel.size_changed.connect(self.size_changed)
        self._panel.opacity_changed.connect(self.opacity_changed)
        self._panel.filled_changed.connect(self.filled_changed)
        self._panel.font_family_changed.connect(self.font_family_changed)
        self._panel.font_size_changed.connect(self.font_size_changed)
        self._panel.font_bold_changed.connect(self.font_bold_changed)
        self._panel.font_italic_changed.connect(self.font_italic_changed)
        self._panel.font_underline_changed.connect(self.font_underline_changed)

        # Set initial page
        self._panel.set_page_for_tool(TOOL_PEN)

    def _on_tool_changed(self, tool):
        self._panel.set_page_for_tool(tool)
        self.tool_changed.emit(tool)

    # Passthrough accessors so the mode can read current UI state
    @property
    def panel(self):
        return self._panel

    @property
    def strip(self):
        return self._strip

    def set_undo_enabled(self, v):
        self._strip.set_undo_enabled(v)

    def set_redo_enabled(self, v):
        self._strip.set_redo_enabled(v)


class AnnotateToolbarDockWidget(QtWidgets.QDockWidget):
    """QDockWidget wrapper for the annotation toolbar."""

    def __init__(self, parent=None):
        super().__init__("Annotations", parent)
        self.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable | QtWidgets.QDockWidget.DockWidgetFloatable)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        self._widget = AnnotateToolbarWidget()
        self.setWidget(self._widget)

    @property
    def toolbar_widget(self):
        return self._widget
