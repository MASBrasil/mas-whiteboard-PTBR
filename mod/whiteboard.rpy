# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues


init 4 python in _fom_whiteboard:
    import pygame
    import store
    import zlib
    import io

    _script_dir = store.fom_getScriptDir(fallback="Submods/Whiteboard", relative=True)
    _assets_dir = _script_dir + "/assets"

    IM_UI_WHITEBOARD = "ui_whiteboard_frame.png"

    IM_ICON_MARKER = _assets_dir + "/icon_tool_marker.png"
    IM_ICON_WIPE = _assets_dir + "/icon_tool_wipe.png"
    IM_CUR_NONE = _assets_dir + "/cur_none.png"

    def _pygame_imload(impath):
        full_path = store.config.gamedir + "/" + _assets_dir + "/" + impath
        return pygame.image.load(full_path)

    # MAS apparently has it None by default
    if store.config.mouse is None:
        store.config.mouse = {}

    class Brush(object):
        """Abstract brush tool for making changes to canvas."""

        def apply(self, surface, mouse_from, mouse_to, buttons_held):
            """
            Applies this brush to surface.
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
            left_held, mh, rh = buttons_held
            if not left_held:
                # Only draw with left mouse
                return

            if m_from != m_to:
                m_from_l = self._adjust_xy(m_from)
                m_to_l = self._adjust_xy(m_to)
                pygame.draw.line(surface, self.color, m_from_l, m_to_l, self.size)

            x, y = self._adjust_xy(m_to)
            pygame.draw.circle(surface, self.color, (x, y), self.size // 2)

        def outline(self, surface, mouse_xy):
            x, y = self._adjust_xy(mouse_xy)
            pygame.draw.circle(surface, (0, 0, 0, 255), (x, y), self.size // 2, 1)

        def increment_size(self):
            self.size = min(self.size + 1, self.max_size)

        def decrement_size(self):
            self.size = max(self.size - 1, self.min_size)

        def _adjust_xy(self, xy, add=(0, 0)):
            return (xy[0] - self.size // 2 + add[0], xy[1] - self.size // 2 + add[1])

    class Wipe(Pencil):
        """Pencil, but with customized defaults."""
        def __init__(self, size=8, min_size=4, max_size=32, color=(255, 255, 255, 255)):
            super(Wipe, self).__init__(size, min_size, max_size, color)

    class Whiteboard(renpy.Displayable):
        """Bare canvas displayable with customizable brush and background,
           custom cursor (on hover) support and save/load functionality.
           Other decorations must be applied as an overlay."""

        def __init__(self, **kwargs):
            renpy.Displayable.__init__(self, **kwargs)

            # Preload assets
            self.im_ui_whiteboard = _pygame_imload(IM_UI_WHITEBOARD).convert_alpha()

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
            if self._m_pressed is not None and any(self._m_pressed):
                if self._m_last_xy and self._m_this_xy:
                    m_buttons = tuple(self._m_pressed)
                    off_x, off_y = self._canvas_offset
                    last_xy = (self._m_last_xy[0] - off_x, self._m_last_xy[1] - off_y)
                    this_xy = (self._m_this_xy[0] - off_x, self._m_this_xy[1] - off_y)
                    self.brush.apply(self._canvas, last_xy, this_xy, m_buttons)
                    self._m_last_xy = self._m_this_xy

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

                # Set initial position if none were held before this event was fired
                if initial_unset:
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

        def to_bytes(self):
            """Saves canvas pixel data as PNG+zlib into byte array."""
            buffer = io.BytesIO()
            pygame.image.save(self._canvas, buffer, "png")
            compressed = zlib.compress(buffer.getvalue(), 4)
            return compressed

        def from_bytes(self, data):
            """Loads canvas pixel data from PNG+zlib from byte array."""
            decompressed = zlib.decompress(data)
            buffer = io.BytesIO(decompressed)
            self._canvas = pygame.image.load(buffer, "png")

        def dispose(self):
            """Runs on-destroy logic when canvas is no longer used.
               NOTE: must be called externally, RenPy does not call this."""
            # Restore original cursor
            self._enable_custom_cursor(enable=False)
            # Unlock mouse buttons
            self._lock_mbuttons(lock=False)


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

                textbutton _("Wipe") action Function(whiteboard.wipe)
                textbutton _("Close") action Return()

screen fom_whiteboard_palette(whiteboard):
    $ is_wipe_tool = isinstance(whiteboard.brush, _fom_whiteboard.Wipe)

    grid 4 2:
        spacing 10

        use fom_whiteboard_palette_button(whiteboard, (255, 0, 0, 255), locked=is_wipe_tool) # Red
        use fom_whiteboard_palette_button(whiteboard, (0, 255, 0, 255), locked=is_wipe_tool) # Green
        use fom_whiteboard_palette_button(whiteboard, (0, 0, 255, 255), locked=is_wipe_tool) # Blue

        use fom_whiteboard_palette_button(whiteboard, (255, 255, 0, 255), locked=is_wipe_tool) # Yellow
        use fom_whiteboard_palette_button(whiteboard, (0, 255, 255, 255), locked=is_wipe_tool) # Cyan
        use fom_whiteboard_palette_button(whiteboard, (255, 0, 255, 255), locked=is_wipe_tool) # Magenta

        use fom_whiteboard_palette_button(whiteboard, (0, 0, 0, 255), locked=is_wipe_tool) # Black
        null # Need it for grid

screen fom_whiteboard_palette_button(whiteboard, color, locked=False):
    button action SetField(whiteboard.brush, "color", color):
        xysize (40, 40)

        # Disable clicking when locked
        sensitive not locked

        if whiteboard.brush.color == color or locked:
            # Use a slightly darker (ligher for black) color for selected color
            if color != (0, 0, 0, 255):
                background Color(color).shade(0.75)
            else:
                background Color(color).tint(0.75)
        else:
            background Color(color)

screen fom_whiteboard_toolbox(whiteboard):
    python:
        brush_marker = _fom_whiteboard.Pencil()
        brush_wipe = _fom_whiteboard.Wipe()

    grid 1 2:
        spacing 10
        use fom_whiteboard_tool_button(whiteboard, brush_marker, _fom_whiteboard.IM_ICON_MARKER)
        use fom_whiteboard_tool_button(whiteboard, brush_wipe, _fom_whiteboard.IM_ICON_WIPE)

screen fom_whiteboard_tool_button(whiteboard, tool, icon_path):
    textbutton "{{image={0}}}".format(icon_path):
        #sensitive whiteboard.brush != tool # No idea why, but this doesn't work :/
        action SetField(whiteboard, "brush", tool)
        xysize (40, 40)
