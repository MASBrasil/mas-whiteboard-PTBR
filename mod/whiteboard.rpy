# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues


init 4 python in _fom_whiteboard:
    import collections
    import colorsys
    import pygame
    import store
    import zlib
    import io
    import os
    import re

    script_dir = store.fom_getScriptDir(fallback="Submods/Whiteboard Submod", relative=True)
    assets_dir = script_dir + "/assets"

    IM_UI_WHITEBOARD = os.path.join(store.config.gamedir, assets_dir, "ui_whiteboard_frame.png")

    IM_CANVAS_SAVED_DIR = store.config.renpy_base
    IM_CANVAS_SAVED_NAME_FORMAT = "whiteboard{0:04}.png"

    # NOTE: do not use 'os.path' here, RenPy hates Windows backslashes
    IM_ICON_MARKER = assets_dir + "/icon_tool_marker.png"
    IM_ICON_FILL = assets_dir + "/icon_tool_fill.png"
    IM_ICON_WIPE = assets_dir + "/icon_tool_wipe.png"
    IM_ICON_PALETTE = assets_dir + "/icon_color_palette.png"
    IM_CUR_NONE = assets_dir + "/cur_none.png"

    # MAS apparently has it None by default
    if store.config.mouse is None:
        store.config.mouse = {}

    class Brush(object):
        """Abstract brush tool for making changes to canvas."""

        def apply(self, surface, mouse_from, mouse_to, buttons_held):
            """
            Invoked on every mouse movement, even if no mouse buttons are held.
            Parameters:
            - surface: pygame surface to apply brush to
            - mouse_from: (x, y) tuple of previous mouse position
            - mouse_to: (x, y) tuple of current mouse position
            - buttons_held: (left, middle, right) tuple of boolean mouse
                button states (True if held, False otherwise)
            """

        def outline(self, surface, mouse_xy):
            """
            Applies outline of the next stroke to the surface.
            Parameters:
            - surface: pygame surface to apply brush outline to
            - mouse_xy: (x, y) tuple of current mouse position
            """

        def cursor(self):
            """
            Defines hardware mouse (see RenPy docs) representing this brush.
            Returns (path, x, y) cursor parameters or None.
            If None, default mouse cursor is used.
            """
            return IM_CUR_NONE, 0, 0

        def increment_size(self):
            """
            Defines optional logic for brush size incrementing (mouse wheel up.)
            """

        def decrement_size(self):
            """
            Defines optional logic for brush size decrementing (mouse wheel down.)
            """

    class Pencil(Brush):
        """Simple brush that draws circles of given size and color under
           the cursor and uses lines for interpolated strokes."""

        def __init__(self, size=4, min_size=2, max_size=32, color=(0, 0, 0, 255)):
            super(Pencil, self).__init__(size, color)
            self.size = size
            self.color = color
            self.min_size = min_size
            self.max_size = max_size

        def apply(self, surface, m_from, m_to, buttons_held):
            if not buttons_held:
                # No-op if no buttons are pressed
                return

            left_held, mh, rh = buttons_held
            if not left_held:
                # Only draw with left mouse button
                return

            if m_from != m_to:
                pygame.draw.line(surface, self.color, m_from, m_to, self.size)

            pygame.draw.circle(surface, self.color, m_from, self.size // 2)
            pygame.draw.circle(surface, self.color, m_to, self.size // 2)

        def outline(self, surface, mouse_xy):
            pygame.draw.circle(surface, (0, 0, 0, 255), mouse_xy, self.size // 2, 1)

        def increment_size(self):
            self.size = min(self.size + 1, self.max_size)

        def decrement_size(self):
            self.size = max(self.size - 1, self.min_size)

    class Wipe(Pencil):
        """Pencil, but with customized defaults."""
        def __init__(self, size=8, min_size=4, max_size=32, color=(255, 255, 255, 255)):
            super(Wipe, self).__init__(size, min_size, max_size, color)

    class Fill(Brush):
        """Flood-fill tool."""

        def __init__(self, color=(0, 0, 0, 255)):
            super(Fill, self).__init__()
            self.color = color
            self._lock = False

        def apply(self, surface, m_from, m_to, buttons_held):
            if not buttons_held:
                # Reset lock when no buttons are held
                self._lock = False
                return

            left_held, mh, rh = buttons_held
            if not left_held or self._lock:
                # Only respond to left moust button click unless locked
                return

            w, h = surface.get_size()
            if not (0 <= m_to[0] < w) or not (0 <= m_to[1] < h):
                # Safeguard against attempts to apply outside canvas
                return

            target_color = surface.get_at(m_to)
            if target_color == self.color:
                # No-op when applied on the same color
                return

            queue = collections.deque()
            queue.append(m_to)
            surface.set_at(m_to, self.color) # apply to the center

            # Apply flood fill
            while queue:
                cx, cy = queue.popleft()
                for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        if surface.get_at((nx, ny)) == target_color:
                            surface.set_at((nx, ny), self.color)
                            queue.append((nx, ny))

            self._lock = True

        def outline(self, surface, mouse_xy):
            x, y = mouse_xy
            pygame.draw.line(surface, self.color, (x - 5, y), (x + 5, y), 1)
            pygame.draw.line(surface, self.color, (x, y - 5), (x, y + 5), 1)

    class Whiteboard(renpy.Displayable):
        """Bare canvas displayable with customizable brush and background,
           custom cursor (on hover) support and save/load functionality.
           Other decorations must be applied as an overlay."""

        def __init__(self, **kwargs):
            renpy.Displayable.__init__(self, **kwargs)

            # Preload assets
            self.im_ui_whiteboard = pygame.image.load(IM_UI_WHITEBOARD).convert_alpha()

            # Current brush and background
            self.brush = Pencil()
            self.background = (255, 255, 255, 255)

            # Canvas surface and displayable dimensions (available at first render)
            self._canvas_dim = (720, 480)
            self._canvas_offset = (15, 18) # because of the frame
            self._canvas = None
            self._dim = None

            # Mouse position, hover and press state
            self._m_pressed = None
            self._m_hover = None
            self._m_last_xy = None
            self._m_this_xy = None

            # Mouse custom cursor initial state to restore
            self._m_og_cur = store.config.mouse.get("default", None)
            # Whether to capture all mouse events or not
            self._m_cap_all = False

            # History buffer
            self._history_lock = False
            self._history = []
            self._redo = []
            self._max_history = 20

        def render(self, width, height, st, at):
            self._dim = (width, height)

            # Prepare renderer and canvas surface
            r = renpy.Render(width, height)
            surf = r.canvas().get_surface()

            # Initialize and reset canvas surface to white
            if self._canvas is None:
                self._canvas = pygame.Surface(self._canvas_dim)
                self.wipe()

            # Apply (and interpolate) brush while any mouse button is held
            if self._m_last_xy and self._m_this_xy:
                off_x, off_y = self._canvas_offset
                last_xy = (self._m_last_xy[0] - off_x, self._m_last_xy[1] - off_y)
                this_xy = (self._m_this_xy[0] - off_x, self._m_this_xy[1] - off_y)
                m_buttons = tuple(self._m_pressed)
                self.brush.apply(self._canvas, last_xy, this_xy, m_buttons)
                self._m_last_xy = self._m_this_xy

            # Alternatively, attempt to apply just at the spot
            # This is necessary e.g. for a fill tool, which otherwise will not
            # be able to release its lock after mouse button was released
            elif self._m_this_xy:
                off_x, off_y = self._canvas_offset
                this_xy = (self._m_this_xy[0] - off_x, self._m_this_xy[1] - off_y)
                m_buttons = tuple(self._m_pressed) if self._m_pressed else None
                self.brush.apply(self._canvas, this_xy, this_xy, m_buttons)

            # Blit updated canvas surface
            surf.blit(self._canvas, self._canvas_offset)

            # Draw brush outline at cursor (when over canvas)
            if self._m_this_xy and self._is_cur_over_canvas(self._m_this_xy):
                self.brush.outline(surf, self._m_this_xy)

            # Draw frame
            surf.blit(self.im_ui_whiteboard, (0, 0))

            # Redraw next frame immediately
            renpy.redraw(self, 0)
            return r

        def event(self, ev, x, y, st):
            if ev.type == pygame.MOUSEBUTTONDOWN:
                # Update pressed buttons tuple
                initial_unset = self._m_pressed is None or not any(self._m_pressed)
                if self._m_pressed is None:
                    self._m_pressed = [False for _ in range(1, 4)]
                if ev.button < 4:
                    self._m_pressed[ev.button - 1] = True

                if ev.button == 4:
                    self.brush.increment_size()
                elif ev.button == 5:
                    self.brush.decrement_size()

                # Save snapshot before applying a brush
                if initial_unset and ev.button < 4:
                    self._push_history()

                # Set initial position if none were held before this event was fired
                if initial_unset:
                    # Prevent undo/redo during active brush stroke
                    self._history_lock = True
                    self._m_this_xy = (x, y)
                    self._m_last_xy = (x, y)

                if self._m_hover and self._m_cap_all:
                    # Prevent passing event to keymap
                    raise renpy.IgnoreEvent

            elif ev.type == pygame.MOUSEBUTTONUP:
                # Update pressed buttons tuple
                if self._m_pressed is not None and ev.button < 4:
                    self._m_pressed[ev.button - 1] = False

                    # When no mouse buttons are held, reset mouse state and positions
                    if not any(self._m_pressed):
                        # Reset history lock
                        self._history_lock = False
                        self._m_pressed = None
                        self._m_this_xy = None
                        self._m_last_xy = None

                if self._m_hover and self._m_cap_all:
                    # Prevent passing event to keymap
                    raise renpy.IgnoreEvent

            elif ev.type == pygame.MOUSEMOTION:
                # Update mouse position while moving event when no mouse button is held
                self._m_this_xy = (x, y)

                if self._dim is not None:
                    w, h = self._dim
                    off_x, off_y = self._canvas_offset
                    self._m_hover = self._is_cur_over_canvas((x, y))

                    # Use custom brush cursor (if available) when hovering over
                    # canvas surface only
                    self._enable_custom_cursor(enable=self._m_hover)
                    # Lock mouse buttons only when hovering over canvas
                    self._lock_mbuttons(lock=self._m_hover)

        def wipe(self):
            """Reset canvas to currently set background color fill."""
            self._canvas.fill(self.background)

        def save_as_png(self):
            """
            Saves canvas pixel data as PNG at the saved pictures folder.
            Attempts to store the filename with least available number suffix
            starting with 1.
            """

            filenum = 1
            while True:
                filename = IM_CANVAS_SAVED_NAME_FORMAT.format(filenum)
                filepath = os.path.join(IM_CANVAS_SAVED_DIR, filename)
                if os.path.exists(filepath):
                    filenum += 1
                else:
                    break

            temp_surf = pygame.Surface(self._canvas.get_size()).convert_alpha()
            temp_surf.blit(self._canvas, (0, 0))

            filepath = os.path.abspath(filepath)
            pygame.image.save(temp_surf, filepath)
            renpy.notify(_("Saved whiteboard as {0}.").format(filepath))

        def dispose(self):
            """
            Runs on-destroy logic when canvas is no longer used.
            NOTE: must be called externally, RenPy does not call this.
            """

            # Restore original cursor
            self._enable_custom_cursor(enable=False)
            # Unlock mouse buttons
            self._lock_mbuttons(lock=False)

        def undo(self):
            if not self._history or self._history_lock:
                return

            self._redo.append(self._canvas.copy())
            self._canvas = self._history.pop()

        def redo(self):
            if not self._redo or self._history_lock:
                return

            self._history.append(self._canvas.copy())
            self._canvas = self._redo.pop()


        # Private methods

        def _enable_custom_cursor(self, enable):
            """Enables or disables custom brush cursor (globally, hover check
               is caller's responsibility) if available. No-op if enable=False
               or if custom cursor is unavailable."""

            prev_value = store.config.mouse.get("default", None)
            # If no custom cursor or it is disabled, restore original
            new_value = (enable and [self.brush.cursor()]) or self._m_og_cur

            # Only update mouse if value changes
            has_changed = new_value != prev_value
            if has_changed:
                store.config.mouse["default"] = new_value
                if new_value is None:
                    del store.config.mouse["default"]

        def _lock_mbuttons(self, lock):
            """Locks all mouse buttons (mouse2/mouse3) and captures
               all mouse events instead of passing it to MAS and hiding all screens."""
            self._m_cap_all = lock

        def _is_cur_over_canvas(self, cur_xy):
            """Checks whether given cursor (x,y) is over the canvas area
               (without frame; used to prevent rendering pen/outline over transparent corners.)"""
            off_x, off_y = self._canvas_offset
            w, h = self._dim
            x, y = cur_xy
            return ((x >= off_x and y >= off_y) and
                    (x < w - off_x and y < h - off_y))

        def _push_history(self):
            snap = self._canvas.copy()
            self._history.append(snap)
            self._redo = []
            if len(self._history) > self._max_history:
                self._history.pop(0)

    class ColorPicker(renpy.Displayable):
        """
        A color picker displayable to select custom color instead of
        predefined set of color buttons.
        """

        def __init__(self):
            super(ColorPicker, self).__init__()
            self.selected = (0, 0, 0)
            self._size = None
            self._hue = 0
            self._sat = 1.0
            self._val = 1.0

            # store click coordinates
            self._last_mx = None
            self._last_my = None

            # Surface cache
            self._surf = None

        def render(self, width, height, st, at):
            self._size = (width, height)
            if self._surf is None:
                self._make_gradient()

            r = renpy.Render(width, height)
            surf = r.canvas().get_surface()
            surf.blit(self._surf, (0, 0))

            # Draw the crosshair at the current selection
            if self._last_mx is not None and self._last_my is not None:
                pygame.draw.line(surf, (0, 0, 0), (self._last_mx - 5, self._last_my), (self._last_mx + 5, self._last_my), 1)
                pygame.draw.line(surf, (0, 0, 0), (self._last_mx, self._last_my - 5), (self._last_mx, self._last_my + 5), 1)

            return r

        def event(self, ev, x, y, st):
            w, h = self._size

            # Mouse drag
            if ((ev.type == pygame.MOUSEMOTION and ev.buttons[0] == 1) or
                (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1)): # left button held

                if 0 <= x < w and 0 <= y < h:
                    gradient_width = w - 10
                    if x < gradient_width:
                        self._hue = 360.0 * x / gradient_width
                        self._sat = 1.0 - y / h
                        self.selected = self._hsv_to_rgb(self._hue, self._sat, self._val)
                    else:
                        gval = int(255 * (1.0 - y / h))
                        self.selected = (gval, gval, gval)

                    self._last_mx = x
                    self._last_my = y
                    renpy.restart_interaction()

            renpy.redraw(self, 0)
            return None

        @staticmethod
        def from_clipboard(whiteboard):
            data = pygame.scrap.get(pygame.SCRAP_TEXT)

            if not data:
                renpy.notify(_("Clipboard is empty!"))
                return

            s = data.decode("utf-8", errors="ignore").strip()
            color = None

            re_rgb  = re.findall(r'^rgb\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$', s)
            re_rgba = re.findall(r'^rgba\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*\)$', s)
            re_hex  = re.findall(r'^#?([A-Fa-f0-9]{3}|[A-Fa-f0-9]{6})$', s)

            if re_rgb or re_rgba:
                nums = (re_rgb or re_rgba)[0]
                color = tuple(int(n) for n in nums[:3])
            elif re_hex:
                hexstr = re_hex[0]
                if len(hexstr) == 3:
                    r, g, b = hexstr
                    color = (int(r+r, 16), int(g+g, 16), int(b+b, 16))
                elif len(hexstr) == 6:
                    color = (
                        int(hexstr[0:2], 16),
                        int(hexstr[2:4], 16),
                        int(hexstr[4:6], 16),
                    )

            if color is not None:
                color_hex = "".join("{:02x}".format(c) for c in color)
                renpy.notify(_("Set color from clipboard: {color=" + color_hex + "}" + s + "{/color}"))
                whiteboard.brush.color = color
            else:
                renpy.notify(_("Unknown color format: {0}").format(s[:16]))

        def _hsv_to_rgb(self, h, s, v):
            r, g, b = colorsys.hsv_to_rgb(h/360.0, s, v)
            r = int(min(max(r * 255, 0), 255))
            g = int(min(max(g * 255, 0), 255))
            b = int(min(max(b * 255, 0), 255))
            return r, g, b

        def _make_gradient(self):
            surf = pygame.Surface(self._size)
            w, h = self._size

            gradient_width = int(w - 10)
            gray_width = 10

            for x in range(gradient_width):
                for y in range(int(h)):
                    hue = 360.0 * x / gradient_width
                    sat = 1.0 - y / h
                    r, g, b = colorsys.hsv_to_rgb(hue/360.0, sat, self._val)
                    r = int(min(max(r*255, 0), 255))
                    g = int(min(max(g*255, 0), 255))
                    b = int(min(max(b*255, 0), 255))
                    surf.set_at((x, y), (r, g, b))

            for x in range(gradient_width, int(w)):
                for y in range(int(h)):
                    gval = int(255 * (1.0 - y / h))
                    surf.set_at((x, y), (gval, gval, gval))

            self._surf = surf


# Displayable styles (copypaste from MAS mainly)

style fom_whiteboard_button is generic_button_light:
    xysize (116, None)
    padding (10, 5, 10, 5)

style fom_whiteboard_button_dark is generic_button_dark:
    xysize (116, None)
    padding (10, 5, 10, 5)

style fom_whiteboard_button_text is generic_button_text_light:
    text_align 0.5
    layout "subtitle"

style fom_whiteboard_button_text_dark is generic_button_text_dark:
    text_align 0.5
    layout "subtitle"


# Screen and displayables

screen fom_whiteboard_screen(whiteboard):
    key "ctrl_K_z" action Function(whiteboard.undo)
    key "ctrl_K_y" action Function(whiteboard.redo)

    vbox:
        style_prefix "fom_whiteboard"
        align (0.5, 0.5)
        spacing 10

        hbox:
            xalign 0.5
            xsize 750
            ysize 512
            add whiteboard

        hbox:
            xsize 720
            xalign 0.5

            use fom_whiteboard_toolbox(whiteboard)
            use fom_whiteboard_palette(whiteboard)

            vbox:
                spacing 10
                xalign 1.0

                textbutton _("Clear") action Function(whiteboard.wipe)
                textbutton _("Save") action Function(whiteboard.save_as_png)
                textbutton _("Close") action Return()

screen fom_whiteboard_palette(whiteboard):
    grid 4 2:
        spacing 10

        use fom_whiteboard_palette_button(whiteboard, (255, 0, 0, 255)) # Red
        use fom_whiteboard_palette_button(whiteboard, (0, 255, 0, 255)) # Green
        use fom_whiteboard_palette_button(whiteboard, (0, 0, 255, 255)) # Blue

        use fom_whiteboard_palette_button(whiteboard, (255, 255, 0, 255)) # Yellow
        use fom_whiteboard_palette_button(whiteboard, (0, 255, 255, 255)) # Cyan
        use fom_whiteboard_palette_button(whiteboard, (255, 0, 255, 255)) # Magenta

        use fom_whiteboard_palette_button(whiteboard, (0, 0, 0, 255)) # Black
        use fom_whiteboard_palette_button_picker(whiteboard) # Color picker

screen fom_whiteboard_palette_button(whiteboard, color):
    # To change color on hover
    default is_hovered = False
    default active_tint = 0.75
    default hover_tint = 0.85

    # Not the best way to approach that with targeting Wipe specifically...
    $ is_wipe_tool = isinstance(whiteboard.brush, _fom_whiteboard.Wipe)
    $ is_selected = whiteboard.brush.color == color

    button action SetField(whiteboard.brush, "color", color):
        xysize (40, 40)

        # Disable selecting a color when using wipe tool
        sensitive not (is_wipe_tool or is_selected)
        hovered _fom_rpy_backports.ToggleLocalVariable("is_hovered")
        unhovered _fom_rpy_backports.ToggleLocalVariable("is_hovered")

        if is_wipe_tool or is_selected:
            # Use a slightly darker (ligher for black) shade for selected color
            if color != (0, 0, 0, 255):
                background Color(color).shade(active_tint)
            else:
                background Color(color).tint(active_tint)
        elif is_hovered:
            if color != (0, 0, 0, 255):
                background Color(color).shade(hover_tint)
            else:
                background Color(color).tint(hover_tint)
        else:
            background Color(color)

screen fom_whiteboard_palette_button_picker(whiteboard):
    $ is_wipe_tool = isinstance(whiteboard.brush, _fom_whiteboard.Wipe)
    textbutton "{{image={0}}}".format(_fom_whiteboard.IM_ICON_PALETTE):
        xysize (40, 40)
        action Show("fom_whiteboard_color_picker", None, whiteboard)
        # Disable selecting a color when using wipe tool
        sensitive not is_wipe_tool

screen fom_whiteboard_toolbox(whiteboard):
    # Copy a reference from the whiteboard so it's properly grayed out initially
    default brush_pencil = whiteboard.brush
    default brush_fill = _fom_whiteboard.Fill()
    default brush_wipe = _fom_whiteboard.Wipe()

    grid 2 2:
        spacing 10
        use fom_whiteboard_tool_button(whiteboard, brush_pencil, _fom_whiteboard.IM_ICON_MARKER)
        use fom_whiteboard_tool_button(whiteboard, brush_fill, _fom_whiteboard.IM_ICON_FILL)
        use fom_whiteboard_tool_button(whiteboard, brush_wipe, _fom_whiteboard.IM_ICON_WIPE)
        null # spacing

screen fom_whiteboard_tool_button(whiteboard, tool, icon_path):
    textbutton "{{image={0}}}".format(icon_path):
        sensitive whiteboard.brush != tool
        action SetField(whiteboard, "brush", tool)
        xysize (40, 40)

screen fom_whiteboard_color_picker(whiteboard):
    default picker = _fom_whiteboard.ColorPicker()

    key "ctrl_K_v" action [Function(picker.from_clipboard, whiteboard), Hide("fom_whiteboard_color_picker")]

    style_prefix "fom_whiteboard"
    zorder 100
    modal True

    frame:
        xalign 0.45
        yalign 0.9
        padding (20, 20, 20, 20)

        vbox:
            xsize 240
            ysize 150
            spacing 10

            add picker

            hbox:
                spacing 10
                textbutton "OK" action [SetField(whiteboard.brush, "color", picker.selected), Hide("fom_whiteboard_color_picker")]
                textbutton "Cancel" action [Hide("fom_whiteboard_color_picker")]
