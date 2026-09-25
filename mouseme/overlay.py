import cairo
from gi.repository import Gdk, Gio, GLib, Gtk

WIDTH = 234
FONT_FAMILY = "Monospace"
FONT_SIZE = 15

# Height used when there's no top bar to fit into
DEFAULT_HEIGHT = 27

# Gap between the end of the text and the top bar's tray and system icons
TRAY_GAP = 12

# Used when GNOME Shell can't say where the icons start: the text ends this far from the right edge,
# leaving room for the icons to grow leftward
RIGHT_MARGIN = 300

# Where the top bar's right-hand box (tray and system icons) starts, in root-window pixels
_TRAY_X_SCRIPT = "Main.panel._rightBox.get_transformed_position()[0]"


# Borderless, click-through status text in the top bar, next to the tray, that never takes focus from the game.
# The counterpart of the macOS menu bar item and the text over the Windows taskbar.
# Every method is safe to call from any thread; the window itself only lives on the GTK thread.
class OverlayPanel:
    def __init__(self):
        self._window = None
        self._text = ""
        self._color = "#ff3b30"
        self._height = DEFAULT_HEIGHT

    def show(self):
        GLib.idle_add(self._show)

    def close(self):
        GLib.idle_add(self._close)

    def set_text(self, text):
        self.set(text, None)

    def set(self, text, color):
        GLib.idle_add(self._set, text, color)

    # MARK: - GTK thread

    def _show(self):
        # A popup is override-redirect: the window manager never focuses, decorates or lists it
        window = Gtk.Window(type=Gtk.WindowType.POPUP)
        window.set_app_paintable(True)
        window.set_accept_focus(False)
        window.set_keep_above(True)

        screen = window.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            window.set_visual(visual)

        window.connect("draw", self._draw)
        window.connect("realize", lambda w: w.input_shape_combine_region(cairo.Region()))

        x, y, self._height = self._frame(window)
        window.set_default_size(WIDTH, self._height)
        window.move(x, y)
        window.show()
        self._window = window
        return False

    def _close(self):
        if self._window is not None:
            self._window.destroy()
            self._window = None
        return False

    def _set(self, text, color):
        self._text = text
        if color is not None:
            self._color = color

        if self._window is not None:
            self._window.queue_draw()
        return False

    # Covers the top bar's strip (the gap above the work area), ending just left of the tray and system icons
    @staticmethod
    def _frame(window):
        display = window.get_display()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        frame = monitor.get_geometry()
        visible = monitor.get_workarea()

        top_bar_height = visible.y - frame.y
        height = top_bar_height if top_bar_height > 0 else DEFAULT_HEIGHT

        right = frame.x + frame.width - RIGHT_MARGIN
        tray_x = _tray_x()
        if tray_x is not None and frame.x + WIDTH < tray_x <= frame.x + frame.width:
            right = tray_x - TRAY_GAP

        return right - WIDTH, frame.y, height

    def _draw(self, window, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if not self._text:
            return False

        cr.select_font_face(FONT_FAMILY, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(FONT_SIZE)

        extents = cr.font_extents()
        baseline = (self._height + extents[0] - extents[1]) / 2

        # Right-aligned so longer text grows away from the tray
        x = WIDTH - cr.text_extents(self._text).x_advance - 2

        # Black outline standing in for the macOS text shadow, so the text reads on any background
        cr.move_to(x, baseline)
        cr.text_path(self._text)
        cr.set_source_rgba(0, 0, 0, 0.9)
        cr.set_line_width(2)
        cr.stroke()

        color = Gdk.RGBA()
        color.parse(self._color)
        cr.set_source_rgba(color.red, color.green, color.blue, 1)
        cr.move_to(x, baseline)
        cr.show_text(self._text)
        return False


# Asks GNOME Shell where its tray and system icons start. Returns None outside GNOME, or on GNOME 41 and later,
# which only answer this call in unsafe mode.
def _tray_x():
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        result = bus.call_sync(
            "org.gnome.Shell", "/org/gnome/Shell", "org.gnome.Shell", "Eval",
            GLib.Variant("(s)", (_TRAY_X_SCRIPT,)), GLib.VariantType("(bs)"),
            Gio.DBusCallFlags.NONE, 500, None)
        ok, value = result.unpack()
        return int(float(value)) if ok else None
    except (GLib.Error, ValueError):
        return None
