# Copyright (c) 2025 Autodesk, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import math
import os
import uuid

from rv import commands

from annotate_toolbar_widget import (
    TOOL_RECT,
    TOOL_CIRCLE,
    TOOL_ARROW,
    TOOL_LINE,
    TOOL_TEXT,
)

_SHAPE_TOOLS = {TOOL_RECT, TOOL_CIRCLE, TOOL_ARROW, TOOL_LINE}
_DRAWING_TOOLS = _SHAPE_TOOLS | {TOOL_TEXT}

TABLE_NAME = "annotate_toolbar_shape"

_PREFIX = {
    TOOL_RECT: "rect",
    TOOL_CIRCLE: "ellipse",
    TOOL_ARROW: "arrow",
    TOOL_LINE: "line",
}

_SIZE_SCALE = 1.0 / 10000.0
_SIZE_MIN = 0.001

_FONT_SIZE_PX = {"small": 16.0, "medium": 24.0, "large": 36.0}

# US keyboard shift-symbol mapping used for text input
_SHIFT_MAP = {
    "1": "!",
    "2": "@",
    "3": "#",
    "4": "$",
    "5": "%",
    "6": "^",
    "7": "&",
    "8": "*",
    "9": "(",
    "0": ")",
    "-": "_",
    "=": "+",
    "[": "{",
    "]": "}",
    "\\": "|",
    ";": ":",
    "'": '"',
    ",": "<",
    ".": ">",
    "/": "?",
    "`": "~",
}


class AnnotateDrawEngine:
    def __init__(self, mode):
        self._mode = mode

        # Shape drag state
        self._anchor = None
        self._last_pei = None
        self._current_shape = None
        self._current_node = None
        self._current_frame = None
        self._shape_type = None
        self._shape_active = False
        self._shift_transition = False
        self._constraint_angle = None

        # Text editing state
        self._text_active = False
        self._text_buffer = ""
        self._text_node = None  # full property path
        self._text_paint_node = None
        self._text_frame = None

    # ------------------------------------------------------------------
    # Event table setup
    # ------------------------------------------------------------------

    def setup_event_table(self, mode):
        mode.defineEventTable(TABLE_NAME, self.bindings)
        mode.defineEventTableRegex(TABLE_NAME, self.regex_bindings)

    @property
    def bindings(self):
        return [
            # Shape pointer events
            ("pointer-1--push", self.on_push, "Start shape/text"),
            ("pointer-1--drag", self.on_drag, "Update shape"),
            ("pointer-1--release", self.on_release, "Commit shape"),
            ("pointer-1--shift--push", self.on_push_shift, "Start shape (constrained)"),
            ("pointer-1--shift--drag", self.on_drag_shift, "Update shape (constrained)"),
            ("pointer-1--shift--release", self.on_release_shift, "Commit shape (constrained)"),
            ("stylus-pen--push", self.on_push, "Start (stylus)"),
            ("stylus-pen--drag", self.on_drag, "Update (stylus)"),
            ("stylus-pen--release", self.on_release, "Commit (stylus)"),
            # Shape shift-constraint tracking
            ("key-down--shift--shift", self.on_shift_down, "Constrain shape"),
            ("key-up--shift", self.on_shift_up, "Release constraint"),
            # Text editing — explicit keys
            ("key-down--backspace", self.on_text_backspace, "Delete char"),
            ("key-down--delete", self.on_text_backspace, "Delete char"),
            ("key-down--space", self.on_text_space, "Insert space"),
            ("key-down--return", self.on_text_commit, "Commit text"),
            ("key-down--enter", self.on_text_commit, "Commit text"),
            ("key-down--keypad-enter", self.on_text_commit, "Commit text"),
            ("key-down--escape", self.on_text_cancel, "Cancel text"),
            # Commit when frame changes so text isn't left open during playback
            ("frame-changed", self.on_frame_changed, "Commit text on frame change"),
        ]

    @property
    def regex_bindings(self):
        return [
            (r"^key-down--.$", self.on_text_key, "Insert char"),
            (r"^key-down--shift--.$", self.on_text_key, "Insert shifted char"),
            (r"^key-up--.$", self.on_key_up, "Key up"),
            (r"^key-up--shift--.$", self.on_key_up, "Key up (shift)"),
        ]

    # ------------------------------------------------------------------
    # Public helpers called by the mode
    # ------------------------------------------------------------------

    def update_text_style(self):
        """Update all font properties on the active text node.

        Called whenever the user changes family, size, bold, italic, or underline
        while a text node is being edited so changes apply immediately.
        """
        if not self._text_active or self._text_node is None:
            return
        try:
            font_size = _FONT_SIZE_PX.get(self._mode._font_size, 24.0)
            font_weight = "bold" if self._mode._font_bold else "normal"
            font_style = "italic" if self._mode._font_italic else "normal"
            text_deco = "underline" if self._mode._font_underline else "none"
            commands.setStringProperty(f"{self._text_node}.fontFamily", [self._mode._font_family], True)
            commands.setFloatProperty(f"{self._text_node}.fontSize", [font_size], True)
            commands.setStringProperty(f"{self._text_node}.fontWeight", [font_weight], True)
            commands.setStringProperty(f"{self._text_node}.fontStyle", [font_style], True)
            commands.setStringProperty(f"{self._text_node}.textDecoration", [text_deco], True)
            commands.redraw()
        except Exception as e:
            print(f"[annotate_toolbar] update_text_style error: {e}")

    def commit_text_if_active(self):
        if self._text_active:
            self._commit_text()

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _is_shape_tool(self):
        return self._mode._tool in _SHAPE_TOOLS

    def _border_width(self):
        return max(_SIZE_MIN, self._mode._size * _SIZE_SCALE)

    def _colors(self):
        c = self._mode._colour
        alpha = self._mode._opacity / 100.0
        border = [c.redF(), c.greenF(), c.blueF(), alpha]
        tool = self._mode._tool
        if tool == TOOL_ARROW:
            inner = list(border)
        elif self._mode._filled and tool in (TOOL_RECT, TOOL_CIRCLE):
            inner = list(border)
        else:
            inner = [c.redF(), c.greenF(), c.blueF(), 0.0]
        return border, inner

    # ------------------------------------------------------------------
    # Paint node resolution
    # ------------------------------------------------------------------

    def _find_paint_node(self):
        try:
            frame = commands.frame()
            infos = commands.metaEvaluate(frame, commands.viewNode())
            for info in infos:
                if info.get("nodeType") == "RVPaint":
                    return info["node"], info["frame"]
            all_paint = commands.nodesOfType("RVPaint")
            if all_paint:
                return all_paint[0], frame
            return None, None
        except Exception:
            return None, None

    def _next_id(self, paint_node):
        prop = f"{paint_node}.paint.nextId"
        if not commands.propertyExists(prop):
            commands.newProperty(prop, commands.IntType, 1)
            commands.setIntProperty(prop, [0])
        i = commands.getIntProperty(prop)[0] + 1
        commands.setIntProperty(prop, [i])
        return i

    def _ensure_visible(self, paint_node):
        prop = f"{paint_node}.paint.show"
        if not commands.propertyExists(prop):
            commands.newProperty(prop, commands.IntType, 1)
        commands.setIntProperty(prop, [1], True)

    def _unique_name(self, paint_node, prefix, frame):
        node_id = self._next_id(paint_node)
        host = commands.myNetworkHost().replace(".", "_")
        pid = os.getpid()
        return f"{paint_node}.{prefix}:{node_id}:{frame}:{host}_{pid}"

    def _frame_order_and_undo(self, paint_node, frame, node_name, shape_uuid):
        """Insert the component into the frame draw order and undo stack."""

        def _ensure(prop, ptype, w):
            if not commands.propertyExists(prop):
                commands.newProperty(prop, ptype, w)

        component = node_name.split(".")[-1]
        order_prop = f"{paint_node}.frame:{frame}.order"
        _ensure(order_prop, commands.StringType, 1)
        if component not in commands.getStringProperty(order_prop):
            commands.insertStringProperty(order_prop, [component])

        host = commands.myNetworkHost().replace(".", "_")
        pid = os.getpid()
        undo_prop = f"{paint_node}.frame:{frame}.userUndoStack:{host}_{pid}"
        _ensure(undo_prop, commands.StringType, 1)
        commands.insertStringProperty(undo_prop, [shape_uuid, "create"])

    # ------------------------------------------------------------------
    # Pointer / coordinate helpers
    # ------------------------------------------------------------------

    def _pointer_location(self, event):
        """Return (image_name, _Vec2) in image space, or ("", None).

        imagesAtPixel returns nodes outermost→innermost without the "annotate" tag:
          [displayGroup0_colorPipeline_0, defaultSequence_sequence, sourceGroup_source]
        The first entry (display pipeline) has a zoom-dependent transform that diverges
        from PaintIPNode's source-image coordinate space after zoom/pan.
        Use the LAST "inside" entry (source node) whose space matches PaintIPNode.
        eventToImageSpace takes the DPR-scaled pointer.
        Wrap the result in _Vec2 so callers can use .x/.y.
        """
        try:
            raw = event.pointer()
            dpr = commands.devicePixelRatio()
            ip = (raw[0] * dpr, raw[1] * dpr)

            pinfos = commands.imagesAtPixel(raw)
            if not pinfos:
                return "", None

            # Always use the last (deepest/source) entry regardless of inside status.
            # imagesAtPixel orders outermost→innermost: [displayPipeline, sequence, source].
            # The display node is always "inside" but its coordinate space differs from
            # PaintIPNode's source-image space, causing misplacement after zoom/pan or
            # when drawing in the black border outside the image.
            # The source node gives correct coordinates both inside the image and as
            # extrapolated values outside it, consistent with PaintIPNode's render space.
            info = pinfos[-1]
            name = info["name"]

            pei_raw = commands.eventToImageSpace(name, ip, True)
            return name, _Vec2(pei_raw[0], pei_raw[1])
        except Exception as e:
            import traceback

            print(f"[annotate_toolbar] _pointer_location error: {e}")
            traceback.print_exc()
            return "", None

    # ------------------------------------------------------------------
    # Shape node creation / update
    # ------------------------------------------------------------------

    def _new_shape(self, paint_node, frame, prefix, anchor, cur):
        try:
            self._ensure_visible(paint_node)
            n = self._unique_name(paint_node, prefix, frame)
            bw = self._border_width()
            border, inner = self._colors()
            shape_uuid = str(uuid.uuid4())

            def _ensure(prop, ptype, w):
                if not commands.propertyExists(prop):
                    commands.newProperty(prop, ptype, w)

            _ensure(f"{n}.startFrame", commands.IntType, 1)
            _ensure(f"{n}.duration", commands.IntType, 1)
            _ensure(f"{n}.eye", commands.IntType, 1)
            commands.setIntProperty(f"{n}.startFrame", [frame], True)
            commands.setIntProperty(f"{n}.duration", [1], True)
            commands.setIntProperty(f"{n}.eye", [2], True)

            if prefix in ("rect", "ellipse"):
                for prop, w in ((".min", 2), (".max", 2), (".innerColor", 4), (".borderColor", 4), (".borderWidth", 1)):
                    _ensure(f"{n}{prop}", commands.FloatType, w)
                min_x = min(anchor.x, cur.x)
                min_y = min(anchor.y, cur.y)
                max_x = max(anchor.x, cur.x)
                max_y = max(anchor.y, cur.y)
                commands.setFloatProperty(f"{n}.min", [min_x, min_y], True)
                commands.setFloatProperty(f"{n}.max", [max_x, max_y], True)
                commands.setFloatProperty(f"{n}.innerColor", inner, True)
                commands.setFloatProperty(f"{n}.borderColor", border, True)
                commands.setFloatProperty(f"{n}.borderWidth", [bw], True)
            else:
                for prop, w in ((".startPos", 2), (".endPos", 2), (".borderColor", 4), (".borderWidth", 1)):
                    _ensure(f"{n}{prop}", commands.FloatType, w)
                commands.setFloatProperty(f"{n}.startPos", [anchor.x, anchor.y], True)
                commands.setFloatProperty(f"{n}.endPos", [cur.x, cur.y], True)
                commands.setFloatProperty(f"{n}.borderColor", border, True)
                commands.setFloatProperty(f"{n}.borderWidth", [bw], True)
                if prefix == "arrow":
                    _ensure(f"{n}.innerColor", commands.FloatType, 4)
                    _ensure(f"{n}.thickness", commands.FloatType, 1)
                    commands.setFloatProperty(f"{n}.innerColor", inner, True)
                    commands.setFloatProperty(f"{n}.thickness", [bw], True)

            _ensure(f"{n}.uuid", commands.StringType, 1)
            _ensure(f"{n}.softDeleted", commands.IntType, 1)
            commands.setStringProperty(f"{n}.uuid", [shape_uuid], True)
            commands.setIntProperty(f"{n}.softDeleted", [0], True)

            self._frame_order_and_undo(paint_node, frame, n, shape_uuid)

            commands.redraw()
            return n
        except Exception as e:
            import traceback

            print(f"[annotate_toolbar] _new_shape error: {e}")
            traceback.print_exc()
            return None

    def _update_shape(self, shape_node, prefix, anchor, cur):
        if shape_node is None:
            return
        try:
            if prefix in ("rect", "ellipse"):
                commands.setFloatProperty(f"{shape_node}.min", [min(anchor.x, cur.x), min(anchor.y, cur.y)], True)
                commands.setFloatProperty(f"{shape_node}.max", [max(anchor.x, cur.x), max(anchor.y, cur.y)], True)
            else:
                commands.setFloatProperty(f"{shape_node}.endPos", [cur.x, cur.y], True)
            commands.redraw()
        except Exception as e:
            print(f"[annotate_toolbar] _update_shape error: {e}")

    # ------------------------------------------------------------------
    # Text node creation / update
    # ------------------------------------------------------------------

    def _new_text_node(self, paint_node, frame, pos):
        """Create an empty text node at pos and return its property path."""
        try:
            self._ensure_visible(paint_node)
            n = self._unique_name(paint_node, "text", frame)
            shape_uuid = str(uuid.uuid4())

            c = self._mode._colour
            alpha = self._mode._opacity / 100.0
            color = [c.redF(), c.greenF(), c.blueF(), alpha]

            font_size = _FONT_SIZE_PX.get(self._mode._font_size, 24.0)
            font_weight = "bold" if self._mode._font_bold else "normal"
            font_style = "italic" if self._mode._font_italic else "normal"
            text_deco = "underline" if self._mode._font_underline else "none"

            def _ensure(prop, ptype, w):
                if not commands.propertyExists(prop):
                    commands.newProperty(prop, ptype, w)

            for prop, ptype, w in (
                (".position", commands.FloatType, 2),
                (".color", commands.FloatType, 4),
                (".size", commands.FloatType, 1),
                (".scale", commands.FloatType, 1),
                (".rotation", commands.FloatType, 1),
                (".spacing", commands.FloatType, 1),
                (".font", commands.StringType, 1),
                (".text", commands.StringType, 1),
                (".origin", commands.StringType, 1),
                (".debug", commands.IntType, 1),
                (".startFrame", commands.IntType, 1),
                (".duration", commands.IntType, 1),
                (".mode", commands.IntType, 1),
            ):
                _ensure(f"{n}{prop}", ptype, w)

            commands.setFloatProperty(f"{n}.position", [pos.x, pos.y], True)
            commands.setFloatProperty(f"{n}.color", color, True)
            commands.setFloatProperty(f"{n}.size", [0.01], True)
            commands.setFloatProperty(f"{n}.scale", [1.0], True)
            commands.setFloatProperty(f"{n}.rotation", [0.0], True)
            commands.setFloatProperty(f"{n}.spacing", [0.8], True)
            commands.setStringProperty(f"{n}.font", [""], True)
            commands.setStringProperty(f"{n}.text", ["|"], True)
            commands.setStringProperty(f"{n}.origin", [""], True)
            commands.setIntProperty(f"{n}.debug", [0], True)
            commands.setIntProperty(f"{n}.startFrame", [frame], True)
            commands.setIntProperty(f"{n}.duration", [1], True)
            commands.setIntProperty(f"{n}.mode", [0], True)

            for prop, ptype, w in (
                (".fontFamily", commands.StringType, 1),
                (".fontSize", commands.FloatType, 1),
                (".fontWeight", commands.StringType, 1),
                (".fontStyle", commands.StringType, 1),
                (".textDecoration", commands.StringType, 1),
                (".textAlign", commands.StringType, 1),
            ):
                _ensure(f"{n}{prop}", ptype, w)

            commands.setStringProperty(f"{n}.fontFamily", [self._mode._font_family], True)
            commands.setFloatProperty(f"{n}.fontSize", [font_size], True)
            commands.setStringProperty(f"{n}.fontWeight", [font_weight], True)
            commands.setStringProperty(f"{n}.fontStyle", [font_style], True)
            commands.setStringProperty(f"{n}.textDecoration", [text_deco], True)
            commands.setStringProperty(f"{n}.textAlign", ["left"], True)

            _ensure(f"{n}.uuid", commands.StringType, 1)
            _ensure(f"{n}.softDeleted", commands.IntType, 1)
            commands.setStringProperty(f"{n}.uuid", [shape_uuid], True)
            commands.setIntProperty(f"{n}.softDeleted", [0], True)

            self._frame_order_and_undo(paint_node, frame, n, shape_uuid)
            commands.redraw()
            return n
        except Exception as e:
            import traceback

            print(f"[annotate_toolbar] _new_text_node error: {e}")
            traceback.print_exc()
            return None

    def _update_text_display(self, cursor=True):
        if self._text_node is None:
            return
        display = self._text_buffer + "|" if cursor else self._text_buffer
        try:
            commands.setStringProperty(f"{self._text_node}.text", [display], True)
            commands.redraw()
        except Exception as e:
            print(f"[annotate_toolbar] _update_text_display error: {e}")

    def _commit_text(self):
        self._update_text_display(cursor=False)
        self._text_active = False
        self._text_node = None
        self._text_buffer = ""
        self._text_paint_node = None
        self._text_frame = None
        commands.sendInternalEvent("annotate-text-committed")

    def _cancel_text(self):
        if self._text_node:
            try:
                commands.setIntProperty(f"{self._text_node}.softDeleted", [1], True)
                commands.redraw()
            except Exception:
                pass
        self._text_active = False
        self._text_node = None
        self._text_buffer = ""
        self._text_paint_node = None
        self._text_frame = None

    # ------------------------------------------------------------------
    # Shift constraint (shapes only)
    # ------------------------------------------------------------------

    def _constrain(self, prefix, anchor, cur):
        dx = cur.x - anchor.x
        dy = cur.y - anchor.y
        if prefix in ("rect", "ellipse"):
            if self._constraint_angle is not None:
                cx = math.cos(self._constraint_angle)
                cy = math.sin(self._constraint_angle)
                proj = max(dx * cx + dy * cy, 0.0)
                return _Vec2(anchor.x + proj * cx, anchor.y + proj * cy)
            side = min(abs(dx), abs(dy))
            return _Vec2(
                anchor.x + (side if dx >= 0 else -side),
                anchor.y + (side if dy >= 0 else -side),
            )
        else:
            length = math.sqrt(dx * dx + dy * dy)
            if length < 1e-5:
                return cur
            angle = math.atan2(dy, dx)
            snapped = round(angle / (math.pi / 4)) * (math.pi / 4)
            return _Vec2(
                anchor.x + length * math.cos(snapped),
                anchor.y + length * math.sin(snapped),
            )

    # ------------------------------------------------------------------
    # Common shape push / release
    # ------------------------------------------------------------------

    def _do_push(self, pei, paint_node, frame):
        if commands.isPlaying():
            commands.stop()
            commands.setFrame(frame)
        prefix = _PREFIX[self._mode._tool]
        self._anchor = pei
        self._last_pei = pei
        self._shape_type = prefix
        self._current_node = paint_node
        self._current_frame = frame
        self._shape_active = True
        self._shift_transition = False
        commands.sendInternalEvent("set-current-annotate-mode-node", paint_node)
        self._current_shape = self._new_shape(paint_node, frame, prefix, pei, pei)

    def _do_release(self, pei):
        if pei is not None:
            self._update_shape(self._current_shape, self._shape_type, self._anchor, pei)
        self._shape_active = False
        self._current_shape = None
        commands.sendInternalEvent("annotate-shape-released")
        commands.redraw()

    # ------------------------------------------------------------------
    # Pointer event handlers
    # ------------------------------------------------------------------

    def on_push(self, event):
        if self._mode._tool == TOOL_TEXT:
            # Commit any in-progress text, then start a new placement
            if self._text_active:
                self._commit_text()
            paint_node, frame = self._find_paint_node()
            if paint_node is None:
                return
            name, pei = self._pointer_location(event)
            if not name:
                return
            text_node = self._new_text_node(paint_node, frame, pei)
            if text_node:
                self._text_active = True
                self._text_buffer = ""
                self._text_node = text_node
                self._text_paint_node = paint_node
                self._text_frame = frame
            return

        if not self._is_shape_tool():
            event.reject()
            return
        if self._shift_transition:
            self._shift_transition = False
            return
        paint_node, frame = self._find_paint_node()
        if paint_node is None:
            return
        name, pei = self._pointer_location(event)
        if not name:
            return
        self._constraint_angle = None
        self._do_push(pei, paint_node, frame)

    def on_drag(self, event):
        if self._mode._tool == TOOL_TEXT:
            return  # consume without action during text placement
        if not self._is_shape_tool() or not self._shape_active:
            event.reject()
            return
        name, pei = self._pointer_location(event)
        if not name:
            return
        self._last_pei = pei
        self._update_shape(self._current_shape, self._shape_type, self._anchor, pei)

    def on_release(self, event):
        if self._mode._tool == TOOL_TEXT:
            return
        if not self._is_shape_tool() or not self._shape_active:
            event.reject()
            return
        if self._shift_transition:
            return
        name, pei = self._pointer_location(event)
        self._do_release(pei if name else None)

    def on_push_shift(self, event):
        if self._mode._tool == TOOL_TEXT:
            return
        if not self._is_shape_tool():
            event.reject()
            return
        if self._shift_transition:
            self._shift_transition = False
            return
        paint_node, frame = self._find_paint_node()
        if paint_node is None:
            return
        name, pei = self._pointer_location(event)
        if not name:
            return
        self._constraint_angle = None
        self._do_push(pei, paint_node, frame)

    def on_drag_shift(self, event):
        if self._mode._tool == TOOL_TEXT:
            return
        if not self._is_shape_tool() or not self._shape_active:
            event.reject()
            return
        name, pei = self._pointer_location(event)
        if not name:
            return
        self._last_pei = pei
        self._update_shape(
            self._current_shape, self._shape_type, self._anchor, self._constrain(self._shape_type, self._anchor, pei)
        )

    def on_release_shift(self, event):
        if self._mode._tool == TOOL_TEXT:
            return
        if not self._is_shape_tool() or not self._shape_active:
            event.reject()
            return
        if self._shift_transition:
            return
        name, pei = self._pointer_location(event)
        if name:
            self._do_release(self._constrain(self._shape_type, self._anchor, pei))
        else:
            self._do_release(None)

    def on_shift_down(self, event):
        if self._text_active:
            return  # don't interfere with text shift+letter input
        if self._shape_active and self._anchor and self._last_pei:
            dx = self._last_pei.x - self._anchor.x
            dy = self._last_pei.y - self._anchor.y
            self._constraint_angle = math.atan2(dy, dx)
        self._shift_transition = True

    def on_shift_up(self, event):
        if self._text_active:
            return
        self._constraint_angle = None
        if self._shape_active:
            self._shift_transition = True

    # ------------------------------------------------------------------
    # Text key handlers
    # ------------------------------------------------------------------

    def on_text_key(self, event):
        if not self._text_active:
            event.reject()
            return
        parts = event.name().split("--")
        ch = parts[-1]
        if len(ch) != 1:
            event.reject()
            return
        has_shift = "shift" in parts[:-1]
        if has_shift:
            char = ch.upper() if ch.isalpha() else _SHIFT_MAP.get(ch, ch)
        else:
            char = ch
        self._text_buffer += char
        self._update_text_display(cursor=True)

    def on_text_space(self, event):
        if not self._text_active:
            event.reject()
            return
        self._text_buffer += " "
        self._update_text_display(cursor=True)

    def on_text_backspace(self, event):
        if not self._text_active:
            event.reject()
            return
        if self._text_buffer:
            self._text_buffer = self._text_buffer[:-1]
        self._update_text_display(cursor=True)

    def on_text_commit(self, event):
        if not self._text_active:
            event.reject()
            return
        self._commit_text()

    def on_text_cancel(self, event):
        if not self._text_active:
            event.reject()
            return
        self._cancel_text()

    def on_key_up(self, event):
        # Consume key-up events during text input so they don't propagate
        if not self._text_active:
            event.reject()

    def on_frame_changed(self, event):
        if self._text_active:
            self._commit_text()
        event.reject()  # let normal frame-change handling continue


class _Vec2:
    __slots__ = ("x", "y")

    def __init__(self, x, y):
        self.x = x
        self.y = y
