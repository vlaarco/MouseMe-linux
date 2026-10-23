import math

import cairo
from gi.repository import Gdk, GLib, Gtk

from .engine import RunMode, RunSettings
from .overlay import OverlayPanel
from .settings import SettingsKey

# Window position is saved this long after the window stops moving, not on every pixel of a drag
_SAVE_POSITION_DELAY_MS = 500

# The Tabler "pin" (off, tilted) and "pinned" (on, upright) icons, as lines on a 24 x 24 grid
_PIN_ICON = [
    [(15, 4.5), (11, 8.5), (7, 10), (5.5, 11.5), (12.5, 18.5), (14, 17), (15.5, 13), (19.5, 9)],
    [(9, 15), (4.5, 19.5)],
    [(14.5, 4), (20, 9.5)],
]

_PINNED_ICON = [
    [(9, 4), (9, 10), (7, 14), (7, 16), (17, 16), (17, 14), (15, 10), (15, 4)],
    [(12, 16), (12, 21)],
    [(8, 4), (16, 4)],
]

# The Tabler "atom" icon for QI: two orbits tilted either way around a center dot
def _orbit(degrees):
    # An orbit 23.6 wide and 9.4 tall around the center, tilted by the given angle; sized so the atom spans 3 to 21 like the other icons
    tilt = math.radians(degrees)
    points = []
    for i in range(49):
        t = 2 * math.pi * i / 48
        x, y = 11.8 * math.cos(t), 4.7 * math.sin(t)
        points.append((12 + x * math.cos(tilt) - y * math.sin(tilt), 12 + x * math.sin(tilt) + y * math.cos(tilt)))
    return points


_ATOM_ICON = [_orbit(-45), _orbit(45), [(12, 12), (12, 12.01)]]

# The Tabler "swords" icon for GBG
_SWORDS_ICON = [
    [(21, 3), (21, 8), (10, 17), (6, 21), (3, 18), (7, 14), (16, 3), (21, 3)],
    [(5, 13), (11, 19)],
    [(14.32, 17.32), (18, 21), (21, 18), (17.635, 14.635)],
    [(10, 5.5), (8, 3), (3, 3), (3, 8), (6, 10.5)],
]

_ICON_SIZE = 18


class MainWindow(Gtk.Window):
    def __init__(self, engine, settings, icon_path=None):
        super().__init__(title="MouseMe")
        self._engine = engine
        self._settings = settings

        # Read from the engine thread, so kept as plain values rather than asking GTK
        self.is_minimized = False
        self.is_gbg_checked = False

        self._position = None
        self._save_position_source = None

        self._points_text = self._entry()
        self._start_delay_text = self._entry()
        self._loop_delay_text = self._entry()
        self._delay_text = self._entry()
        self._repetitions_text = self._entry()

        # Fixed GBG values, shown in place of the fields above when GBG or QI is checked
        self._points_gbg_text = self._entry("1", fixed=True)
        self._start_delay_gbg_text = self._entry("500", fixed=True)
        self._loop_delay_gbg_text = self._entry("100", fixed=True)
        self._delay_gbg_text = self._entry("100", fixed=True)
        self._repetitions_gbg_text = self._entry("500", fixed=True)

        self._start_button = Gtk.Button(label="Start")

        # The icon bar along the top of the window: mode icons on the left, window controls on the right
        self._icon_bar = Gtk.Box(spacing=6)
        self._qi_check_box = self._icon_toggle(_ATOM_ICON, _ATOM_ICON)
        self._gbg_check_box = self._icon_toggle(_SWORDS_ICON, _SWORDS_ICON)
        self._pin_button = self._icon_toggle(_PIN_ICON, _PINNED_ICON)

        self._build_ui()
        self._load_settings()

        self.set_resizable(False)
        if icon_path:
            self.set_icon_from_file(icon_path)

        # Fall back to the center of the screen if the saved position is no longer fully on a monitor, such as after unplugging one
        position = settings[SettingsKey.window_position]
        if isinstance(position, list) and len(position) == 2 and self._fits_on_a_monitor(*position):
            self.move(*position)
        else:
            self.set_position(Gtk.WindowPosition.CENTER)

        self.connect("configure-event", self._on_configure)
        self.connect("window-state-event", self._on_window_state)
        self.connect("delete-event", self._on_delete)

    # MARK: - Called from the engine thread

    def create_overlay(self):
        return OverlayPanel()

    def minimize(self):
        # Iconifying hands focus back to the window underneath, which is the game
        GLib.idle_add(self.iconify)

    def restore(self):
        GLib.idle_add(self._restore)

    def _restore(self):
        self.deiconify()
        self.present()
        return False

    def _fits_on_a_monitor(self, x, y):
        if not isinstance(x, int) or not isinstance(y, int):
            return False

        _, size = self.get_preferred_size()
        display = self.get_display()

        for i in range(display.get_n_monitors()):
            area = display.get_monitor(i).get_workarea()
            if area.x <= x and area.y <= y and x + size.width <= area.x + area.width and y + size.height <= area.y + area.height:
                return True

        return False

    # MARK: - UI

    @staticmethod
    def _entry(text="", fixed=False):
        entry = Gtk.Entry(text=text)
        entry.set_width_chars(10)
        entry.set_alignment(1.0)
        entry.set_activates_default(True)
        entry.set_no_show_all(True)

        if fixed:
            entry.set_sensitive(False)
            entry.set_can_focus(False)

        return entry

    def _build_ui(self):
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, margin=12)

        self._qi_check_box.set_tooltip_text("Quantum Incursions mode")
        self._icon_bar.pack_start(self._qi_check_box, False, False, 0)

        self._gbg_check_box.set_tooltip_text("Guild Battlegrounds mode")
        self._icon_bar.pack_start(self._gbg_check_box, False, False, 0)

        self._pin_button.connect("toggled", self._pin_button_changed)
        self._icon_bar.pack_end(self._pin_button, False, False, 0)
        grid.attach(self._icon_bar, 0, 0, 2, 1)

        rows = [
            ("Number of Points", self._points_text, self._points_gbg_text),
            ("Start Delay (ms)", self._start_delay_text, self._start_delay_gbg_text),
            ("Loop Delay (ms)", self._loop_delay_text, self._loop_delay_gbg_text),
            ("Delay (ms)", self._delay_text, self._delay_gbg_text),
            ("Repetitions", self._repetitions_text, self._repetitions_gbg_text),
        ]

        for i, (title, field, gbg_field) in enumerate(rows):
            label = Gtk.Label(label=title, xalign=0)
            grid.attach(label, 0, i + 1, 1, 1)

            cell = Gtk.Box()
            cell.pack_start(field, True, True, 0)
            cell.pack_start(gbg_field, True, True, 0)
            grid.attach(cell, 1, i + 1, 1, 1)


        self._qi_check_box.connect("toggled", self._qi_check_box_changed)
        self._gbg_check_box.connect("toggled", self._gbg_check_box_changed)

        self._start_button.set_can_default(True)
        self._start_button.connect("clicked", self._start_clicked)
        # Spans both columns, from where the labels' text starts to the fields' right edge
        grid.attach(self._start_button, 0, len(rows) + 1, 2, 1)
        label.connect("size-allocate", self._align_start_button)

        self.add(grid)
        self.set_default(self._start_button)
        self._start_button.grab_focus()

    # Labels draw their text slightly inside their edge, so indent the Start button by however far that is
    def _align_start_button(self, label, _allocation):
        offset_x, _ = label.get_layout_offsets()
        ink, _ = label.get_layout().get_pixel_extents()
        text_left = max(offset_x - label.get_allocation().x + ink.x, 0)

        if self._start_button.get_margin_start() != text_left:
            self._start_button.set_margin_start(text_left)

    def _load_settings(self):
        s = self._settings

        self._points_text.set_text(str(s[SettingsKey.points]))
        self._start_delay_text.set_text(str(s[SettingsKey.start_delay]))
        self._loop_delay_text.set_text(str(s[SettingsKey.loop_delay]))
        self._delay_text.set_text(str(s[SettingsKey.delay]))
        self._repetitions_text.set_text(str(s[SettingsKey.repetitions]))

        self._gbg_check_box.set_active(bool(s[SettingsKey.gbg]))
        self._qi_check_box.set_active(bool(s[SettingsKey.qi]) and not self._gbg_check_box.get_active())
        self._update_field_visibility()

        self._pin_button.set_active(bool(s[SettingsKey.stay_on_top]))
        self._apply_stay_on_top()

    # MARK: - Stay on top

    def _pin_button_changed(self, _):
        self._settings[SettingsKey.stay_on_top] = self._pin_button.get_active()
        self._settings.save()
        self._apply_stay_on_top()

    # Stays above every other window, including after a run minimizes and restores it, until the pin is clicked again
    def _apply_stay_on_top(self):
        pinned = self._pin_button.get_active()

        self.set_keep_above(pinned)
        self._pin_button.set_tooltip_text("Stop keeping MouseMe on top" if pinned else "Keep MouseMe on top of other windows")

    # MARK: - Icon bar

    # A flat toggle button drawing off_icon while off and on_icon (in the accent color) while on
    def _icon_toggle(self, off_icon, on_icon):
        button = Gtk.ToggleButton(relief=Gtk.ReliefStyle.NONE)
        area = Gtk.DrawingArea()
        area.set_size_request(_ICON_SIZE, _ICON_SIZE)
        area.connect("draw", self._draw_icon, button, off_icon, on_icon)
        button.add(area)
        button.connect("toggled", lambda _: area.queue_draw())
        return button

    @staticmethod
    def _draw_icon(area, cr, button, off_icon, on_icon):
        on = button.get_active()
        style = button.get_style_context()

        if on:
            found, color = style.lookup_color("theme_selected_bg_color")
            if not found:
                color = Gdk.RGBA(0.21, 0.52, 0.89, 1)
        else:
            color = style.get_color(style.get_state())

        # GTK can give the area more room than the icon needs, so draw it square and centered rather than in the top-left
        width, height = area.get_allocated_width(), area.get_allocated_height()
        size = min(width, height)
        cr.translate((width - size) / 2, (height - size) / 2)
        cr.scale(size / 24, size / 24)
        cr.set_line_width(2)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)

        for line in on_icon if on else off_icon:
            cr.move_to(*line[0])
            for point in line[1:]:
                cr.line_to(*point)

        cr.stroke()
        return False

    def _qi_check_box_changed(self, _):
        if self._qi_check_box.get_active():
            self._gbg_check_box.set_active(False)
            self._start_button.grab_focus()

        self._update_field_visibility()

    def _gbg_check_box_changed(self, _):
        if self._gbg_check_box.get_active():
            self._qi_check_box.set_active(False)
            self._start_button.grab_focus()

        self._update_field_visibility()

    def _update_field_visibility(self):
        self.is_gbg_checked = self._gbg_check_box.get_active()
        show_normal = not self._qi_check_box.get_active() and not self._gbg_check_box.get_active()

        for field in (self._points_text, self._start_delay_text, self._loop_delay_text, self._delay_text, self._repetitions_text):
            field.set_visible(show_normal)

        for field in (self._points_gbg_text, self._start_delay_gbg_text, self._loop_delay_gbg_text, self._delay_gbg_text, self._repetitions_gbg_text):
            field.set_visible(not show_normal)

    # MARK: - Start

    def _start_clicked(self, _):
        is_gbg = self._gbg_check_box.get_active()
        is_qi = self._qi_check_box.get_active()
        settings = RunSettings()

        def parse(field, minimum=None):
            try:
                value = int(field.get_text().strip())
            except ValueError:
                return None

            if minimum is not None and value < minimum:
                return None

            return value

        def fields(specs):
            values = []
            for field, minimum, message in specs:
                value = parse(field, minimum)
                if value is None:
                    self._show_message(message)
                    return None
                values.append(value)
            return values

        if is_gbg:
            values = fields([
                (self._points_gbg_text, None, "Please enter a valid number for Number of Points."),
                (self._start_delay_gbg_text, None, "Please enter a valid number for Start Delay."),
                (self._loop_delay_gbg_text, None, "Please enter a valid number for Loop Delay."),
                (self._delay_gbg_text, None, "Please enter a valid number for Delay."),
                (self._repetitions_gbg_text, None, "Please enter a valid number for Repetitions."),
            ])
            if values is None:
                return
            settings = RunSettings(*values)

        elif not is_qi:
            values = fields([
                (self._points_text, 1, "Please enter a number of 1 or more for Number of Points."),
                (self._start_delay_text, 0, "Please enter a number of 0 or more for Start Delay."),
                (self._loop_delay_text, 0, "Please enter a number of 0 or more for Loop Delay."),
                (self._delay_text, 0, "Please enter a number of 0 or more for Delay."),
                (self._repetitions_text, 1, "Please enter a number of 1 or more for Repetitions."),
            ])
            if values is None:
                return
            settings = RunSettings(*values)

        s = self._settings

        # Only normal mode's values are user-entered; GBG uses fixed values and QI uses none
        if not is_gbg and not is_qi:
            s[SettingsKey.points] = settings.points
            s[SettingsKey.start_delay] = settings.start_delay
            s[SettingsKey.loop_delay] = settings.loop_delay
            s[SettingsKey.delay] = settings.delay
            s[SettingsKey.repetitions] = settings.repetitions

        s[SettingsKey.gbg] = is_gbg
        s[SettingsKey.qi] = is_qi
        s.save()

        mode = RunMode.GBG if is_gbg else RunMode.QI if is_qi else RunMode.NORMAL
        self._engine.post(self._engine.start, mode, settings)

    def _show_message(self, text):
        dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK, text=text)
        dialog.run()
        dialog.destroy()

    # MARK: - Window events

    # Moving or restoring the window cancels a run, the same as on Windows and macOS
    def _on_configure(self, *_):
        position = self.get_position()
        moved = self._position is not None and position != self._position
        self._position = position

        if moved and not self.is_minimized:
            self._engine.post(self._engine.cancel_run)
            self._schedule_save_position()

        return False

    def _on_window_state(self, _, event):
        if event.changed_mask & Gdk.WindowState.ICONIFIED:
            was_minimized = self.is_minimized
            self.is_minimized = bool(event.new_window_state & Gdk.WindowState.ICONIFIED)

            if was_minimized and not self.is_minimized:
                self._engine.post(self._engine.cancel_run)

        return False

    def _schedule_save_position(self):
        if self._save_position_source is not None:
            GLib.source_remove(self._save_position_source)

        self._save_position_source = GLib.timeout_add(_SAVE_POSITION_DELAY_MS, self._save_position)

    def _save_position(self):
        self._save_position_source = None
        if self._position is not None:
            self._settings[SettingsKey.window_position] = list(self._position)
            self._settings.save()
        return False

    def _on_delete(self, *_):
        if self._save_position_source is not None:
            GLib.source_remove(self._save_position_source)
            self._save_position()

        Gtk.main_quit()
        return False
