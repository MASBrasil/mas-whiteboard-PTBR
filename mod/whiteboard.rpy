# This file is part of Whiteboard submod by Friends of Monika.
# Report issues and ask questions at https://github.com/friends-of-monika/mas-whiteboard/issues


init 4 python in _fom_whiteboard:
    import pygame
    import store
    import zlib
    import io

    _script_dir = store.fom_getScriptDir(fallback="Submods/Whiteboard", relative=True)
    _assets_dir = _script_dir + "/assets"

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
            - buttons_held: (left, right, middle) tuple of boolean mouse
                button states (True if held, False otherwise)
            """

        def cursor(self):
            """
            Defines _hardware_ mouse (see RenPy docs) representing this brush.
            Returns (path, x, y) cursor parameters or None.
            If None, default mouse cursor is used.
            """

    class Pencil(Brush):
        """Simple brush that draws rectangles of given size and color under
           the cursor and uses lines for interpolated strokes."""

        def __init__(self, size=4, color=(0, 0, 0, 255)):
            super(Pencil, self).__init__(self)
            self.size = size
            self.color = color

        def apply(self, surface, m_from, m_to, buttons_held):
            left_held, rh, mh = buttons_held
            if not left_held:
                # Only draw with left mouse
                return

            if m_from != m_to:
                pygame.draw.line(surface, self.color, m_from, m_to, self.size)
            else:
                x, y = m_from
                pygame.draw.rect(surface, self.color, (x, y, self.size, self.size))

        def cursor(self):
            return _assets_dir + "/cur_marker.png", 0, 39

    class Whiteboard(renpy.Displayable):
        """Bare canvas displayable with customizable brush and background,
           custom cursor (on hover) support and save/load functionality.
           Other decorations must be applied as an overlay."""

        def __init__(self, **kwargs):
            renpy.Displayable.__init__(self, **kwargs)

            # Current brush and background
            self.brush = Pencil()
            self.background = (255, 255, 255, 255)

            # Canvas surface and displayable dimensions (available at first render)
            self._canvas = None
            self._dim = None

            # Mouse pos & pressed state
            self._m_pressed = False
            self._m_last_xy = None
            self._m_this_xy = None
            # Mouse custom cursor initial state to restore
            self._m_og_cur = dict(store.config.mouse)

        def render(self, width, height, st, at):
            self._dim = (width, height)

            # Initialize and reset canvas surface to white
            if self._canvas is None:
                self._canvas = pygame.Surface((width, height))
                self.wipe()

            # Apply (and interpolate) brush while mouse button is held
            if self._m_pressed and self._m_last_xy and self._m_this_xy:
                self.brush.apply(self._canvas, self._m_last_xy, self._m_this_xy, (True, False, False))
                self._m_last_xy = self._m_this_xy

            # Blit render updated surface, request redrawing immediately
            r = renpy.Render(width, height)
            r.canvas().get_surface().blit(self._canvas, (0, 0))
            renpy.redraw(self, 0)

            return r

        def event(self, ev, x, y, st):
            if ev.type == pygame.MOUSEBUTTONDOWN:
                # Set mouse pressed state if left mouse button is held and
                # set initial mouse position
                if not self._m_pressed and ev.button == 1:
                    self._m_pressed = True
                    self._m_this_xy = (x, y)
                    self._m_last_xy = (x, y)

            elif ev.type == pygame.MOUSEBUTTONUP:
                # When left button is released reset pressed state
                if self._m_pressed and ev.button == 1:
                    self._m_pressed = False

            elif ev.type == pygame.MOUSEMOTION:
                # Use custom brush cursor (if available) when hovering over
                # canvas surface only
                if self._dim is not None:
                    w, h = self._dim
                    is_at_canvas = x >= 0 and y >= 0 and x < w and y < h
                    self._enable_custom_cursor(enable=is_at_canvas)

                # Update mouse position while moving with mouse button held
                if self._m_pressed:
                    self._m_this_xy = (x, y)

        def wipe(self):
            """Reset canvas to currently set background color fill."""
            self._canvas.fill(self.background)

        def to_bytes(self):
            """Saves canvas pixel data as PNG+zlib into byte array."""
            buffer = io.BytesIO()
            pygame.image.save(self._surface, buffer, "png")
            compressed = zlib.compress(buffer.getvalue(), 4)
            return compressed

        def from_bytes(self, data):
            """Loads canvas pixel data from PNG+zlib from byte array."""
            decompressed = zlib.decompress(data)
            buffer = io.BytesIO(decompressed)
            self._surface = pygame.image.load(buffer, "png")

        def dispose(self):
            """Runs on-destroy logic when canvas is no longer used.
               NOTE: must be called externally, RenPy does not call this."""
            # Restore original cursor
            self._enable_custom_cursor(enable=False)

        def _enable_custom_cursor(self, enable):
            """Enables or disables custom brush cursor (globally, hover check
               is caller's responsibility) if available. No-op if enable=False
               or if custom cursor is unavailable."""

            if enable:
                new_cur = self.brush.cursor()
                if new_cur is not None:
                    # Use custom brush cursor if available
                    store.config.mouse["default"] = [new_cur]
                    return

            # If no custom cursor or it is disabled, restore original
            store.config.mouse = dict(self._m_og_cur)


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

screen fom_whiteboard_screen(canvas):
    vbox:
        style_prefix "fom_whiteboard"
        align (0.5, 0.5)
        spacing 10

        frame:
            xalign 0.5
            xsize 800
            ysize 600
            add canvas

        hbox:
            xsize 800

            grid 4 2:
                spacing 10

                use fom_whiteboard_palette_button(canvas, (255, 0, 0, 255)) # Red
                use fom_whiteboard_palette_button(canvas, (0, 255, 0, 255)) # Green
                use fom_whiteboard_palette_button(canvas, (0, 0, 255, 255)) # Blue

                use fom_whiteboard_palette_button(canvas, (255, 255, 0, 255)) # Yellow
                use fom_whiteboard_palette_button(canvas, (0, 255, 255, 255)) # Cyan
                use fom_whiteboard_palette_button(canvas, (255, 0, 255, 255)) # Magenta

                use fom_whiteboard_palette_button(canvas, (0, 0, 0, 255)) # Black
                null # Need it for grid

            vbox:
                spacing 10
                xalign 1.0

                textbutton _("Wipe") action Function(canvas.wipe)
                textbutton _("Close") action Return()


screen fom_whiteboard_palette_button(canvas, color):
    button action SetField(canvas.brush, "color", color):
        xsize 40
        ysize 40

        if canvas.brush.color == color:
            # Use a slightly darker (ligher for black) color for selected color
            if color != (0, 0, 0, 255):
                background Color(color).shade(0.75)
            else:
                background Color(color).tint(0.9)
        else:
            background Color(color)
