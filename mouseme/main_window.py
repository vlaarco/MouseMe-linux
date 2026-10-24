import math

import cairo
from gi.repository import Gdk, GLib, Gtk, Pango

from .engine import RunMode, RunSettings
from .qi_config import ArmyConfig, BuildMenuConfig
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
# The Tabler "crosshair" icon for calibrating: four rounded corners around a plus
_CROSSHAIR_ICON = [
    [(4, 8), (4, 6), (4.152, 5.235), (4.586, 4.586), (5.235, 4.152), (6, 4), (8, 4)],
    [(4, 16), (4, 18), (4.152, 18.765), (4.586, 19.414), (5.235, 19.848), (6, 20), (8, 20)],
    [(16, 4), (18, 4), (18.765, 4.152), (19.414, 4.586), (19.848, 5.235), (20, 6), (20, 8)],
    [(16, 20), (18, 20), (18.765, 19.848), (19.414, 19.414), (19.848, 18.765), (20, 18), (20, 16)],
    [(9, 12), (15, 12)],
    [(12, 9), (12, 15)],
]

_SWORDS_ICON = [
    [(21, 3), (21, 8), (10, 17), (6, 21), (3, 18), (7, 14), (16, 3), (21, 3)],
    [(5, 13), (11, 19)],
    [(14.32, 17.32), (18, 21), (21, 18), (17.635, 14.635)],
    [(10, 5.5), (8, 3), (3, 3), (3, 8), (6, 10.5)],
]

# The Tabler "hammer" icon for Build Menu, with its rounded ends approximated
# A Corinthian helmet for Army, drawn filled: a flat-topped skull with straight sides, narrow eye slits either side of a
# straight nose guard, and cheek guards that pinch in, flare out and come to points beside the open mouth
_HELMET_ICON = [[
    (9.8, 22), (9.8, 12.4), (5.7, 10.8), (5.4, 10), (6, 8.9), (11, 10), (11, 14.2), (13, 14.2),
    (13, 10), (18, 8.9), (18.6, 10), (18.3, 10.8), (14.2, 12.4), (14.2, 22), (15.13, 21.49), (16, 20.91),
    (16.8, 20.25), (17.53, 19.51), (18.2, 18.69), (18.8, 17.8), (18.76, 17.15), (18.69, 16.53), (18.6, 15.95), (18.49, 15.4),
    (18.36, 14.88), (18.2, 14.4), (18.69, 14.07), (19.09, 13.74), (19.4, 13.43), (19.62, 13.11), (19.76, 12.8), (19.8, 12.5),
    (19.8, 9), (19.71, 8.05), (19.45, 7.23), (19.02, 6.53), (18.44, 5.95), (17.7, 5.47), (16.82, 5.1), (15.8, 4.83),
    (14.65, 4.64), (13.38, 4.53), (12, 4.5), (10.62, 4.53), (9.35, 4.64), (8.2, 4.83), (7.18, 5.1), (6.3, 5.47),
    (5.56, 5.95), (4.98, 6.53), (4.55, 7.23), (4.29, 8.05), (4.2, 9), (4.2, 12.5), (4.24, 12.8), (4.38, 13.11),
    (4.6, 13.42), (4.91, 13.74), (5.31, 14.07), (5.8, 14.4), (5.64, 14.88), (5.51, 15.4), (5.4, 15.95), (5.31, 16.53),
    (5.24, 17.15), (5.2, 17.8), (5.8, 18.69), (6.47, 19.51), (7.2, 20.25), (8, 20.91), (8.87, 21.49),
]]

_HAMMER_ICON = [
    [(11.414, 10), (4.031, 17.418), (3.4, 18.9), (4.031, 20.385), (5.52, 21), (7.007, 20.385), (14.414, 13)],
    [(18.121, 15.293), (20.707, 12.707), (21, 12), (20.707, 11.293), (13.121, 3.707), (12.414, 3.414), (11.707, 3.707),
     (9.121, 6.293), (8.828, 7), (9.121, 7.707), (16.707, 15.293), (17.414, 15.586), (18.121, 15.293)],
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
        self.is_stay_on_top = False

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
        self._build_menu_check_box = self._icon_toggle(_HAMMER_ICON, _HAMMER_ICON)
        self._army_check_box = self._icon_toggle(_HELMET_ICON, _HELMET_ICON, filled=True)

        # QI, GBG and Build Menu exclude each other
        self._mode_buttons = [self._qi_check_box, self._gbg_check_box, self._build_menu_check_box, self._army_check_box]

        # Army mode shows its own values in the editable fields, under three different labels; the set not shown is kept here
        self._points_label = Gtk.Label(label="Number of Points", xalign=0)
        self._start_delay_label = Gtk.Label(label="Start Delay (ms)", xalign=0)
        self._loop_delay_label = Gtk.Label(label="Loop Delay (ms)", xalign=0)
        self._showing_army_fields = False
        self._hidden_field_values = []
        self._pin_button = self._icon_toggle(_PIN_ICON, _PINNED_ICON)

        # Arms calibration: the next mode icon clicked is calibrated instead of turned on or off
        self._calibrate_button = self._icon_toggle(_CROSSHAIR_ICON, _CROSSHAIR_ICON)
        self._reverting_mode_button = False

        # Which modes were on when calibration was armed, so they come back when it's disarmed
        self._armed_mode_states = None

        # A line of short messages along the bottom of the window; a newer message replaces an older one
        self._status_label = Gtk.Label(xalign=0)
        self._status_version = 0

        # The overlay's text and colour, mirrored in the status bar while a run is going; empty when nothing is running
        self._run_status_text = ""
        self._run_status_color = ""

        # Set while a message is showing, which takes the place of the run's text or the mode's name until it clears
        self._showing_message = False

        # Set while a QI or Build run is going, when the Start button is Stop
        self._stop_button_shown = False

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
        return OverlayPanel(on_change=self._show_run_status)

    # The calibrated Build Menu and Army spots, or None until all of them have been calibrated
    @property
    def build_menu_targets(self):
        return self._saved_spots(SettingsKey.build_menu_targets, len(BuildMenuConfig.target_keys))

    def save_build_menu_targets(self, targets):
        self._save_spots(SettingsKey.build_menu_targets, targets)

    @property
    def army_targets(self):
        return self._saved_spots(SettingsKey.army_targets, len(ArmyConfig.calibration_prompts))

    def save_army_targets(self, targets):
        self._save_spots(SettingsKey.army_targets, targets)

    @property
    def gbg_target(self):
        spots = self._saved_spots(SettingsKey.gbg_target, 1)
        return None if spots is None else spots[0]

    def save_gbg_target(self, targets):
        self._save_spots(SettingsKey.gbg_target, targets)

    def _saved_spots(self, key, count):
        saved = self._settings[key]
        if isinstance(saved, list) and len(saved) == count and all(isinstance(p, list) and len(p) == 2 for p in saved):
            return [tuple(p) for p in saved]
        return None

    # Updated straight away, so the engine sees the new spots, then written to disk on the GTK thread
    def _save_spots(self, key, spots):
        self._settings[key] = [list(p) for p in spots]
        GLib.idle_add(self._save_settings)

    def _save_settings(self):
        self._settings.save()
        return False

    def minimize(self):
        # Iconifying hands focus back to the window underneath, which is the game; a window pinned on top stays visible
        if not self.is_stay_on_top:
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

        self._build_menu_check_box.set_tooltip_text("Build Menu mode")
        self._icon_bar.pack_start(self._build_menu_check_box, False, False, 0)

        self._army_check_box.set_tooltip_text("Army mode")
        self._icon_bar.pack_start(self._army_check_box, False, False, 0)

        self._pin_button.connect("toggled", self._pin_button_changed)
        self._icon_bar.pack_end(self._pin_button, False, False, 0)

        self._calibrate_button.set_tooltip_text("Calibrate a mode: click this, then the mode's icon")
        self._calibrate_button.connect("toggled", self._calibrate_button_changed)
        self._icon_bar.pack_end(self._calibrate_button, False, False, 0)
        grid.attach(self._icon_bar, 0, 0, 2, 1)

        rows = [
            (self._points_label, self._points_text, self._points_gbg_text),
            (self._start_delay_label, self._start_delay_text, self._start_delay_gbg_text),
            (self._loop_delay_label, self._loop_delay_text, self._loop_delay_gbg_text),
            (Gtk.Label(label="Delay (ms)", xalign=0), self._delay_text, self._delay_gbg_text),
            (Gtk.Label(label="Repetitions", xalign=0), self._repetitions_text, self._repetitions_gbg_text),
        ]

        for i, (label, field, gbg_field) in enumerate(rows):
            grid.attach(label, 0, i + 1, 1, 1)

            cell = Gtk.Box()
            cell.pack_start(field, True, True, 0)
            cell.pack_start(gbg_field, True, True, 0)
            grid.attach(cell, 1, i + 1, 1, 1)


        for button in self._mode_buttons:
            button.connect("toggled", self._mode_changed)

        self._start_button.set_can_default(True)
        self._start_button.connect("clicked", self._start_clicked)
        # Spans both columns, from where the labels' text starts to the fields' right edge
        grid.attach(self._start_button, 0, len(rows) + 1, 2, 1)
        label.connect("size-allocate", self._align_start_button)

        self._status_label.get_style_context().add_class("dim-label")
        self._status_label.set_ellipsize(Pango.EllipsizeMode.END)

        # Keep a line's height even when empty, so the window doesn't change size as messages come and go
        self._status_label.set_size_request(-1, 16)
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_end(12)
        self._status_label.set_margin_top(5)
        self._status_label.set_margin_bottom(7)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.pack_start(grid, False, False, 0)
        content.pack_start(Gtk.Separator(), False, False, 0)
        content.pack_start(self._status_label, False, False, 0)
        self.add(content)
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
        self._hidden_field_values = [
            str(s[key]) for key in (SettingsKey.army_units, SettingsKey.army_delay, SettingsKey.army_close_delay,
                                    SettingsKey.army_click_delay, SettingsKey.army_repetitions)
        ]
        self._start_delay_text.set_text(str(s[SettingsKey.start_delay]))
        self._loop_delay_text.set_text(str(s[SettingsKey.loop_delay]))
        self._delay_text.set_text(str(s[SettingsKey.delay]))
        self._repetitions_text.set_text(str(s[SettingsKey.repetitions]))

        self._gbg_check_box.set_active(bool(s[SettingsKey.gbg]))
        self._qi_check_box.set_active(bool(s[SettingsKey.qi]) and not self._gbg_check_box.get_active())
        self._build_menu_check_box.set_active(bool(s[SettingsKey.build_menu]) and not self._qi_check_box.get_active() and not self._gbg_check_box.get_active())
        self._army_check_box.set_active(bool(s[SettingsKey.army]) and not any(b.get_active() for b in self._mode_buttons[:3]))
        self._update_field_visibility()

        self._pin_button.set_active(bool(s[SettingsKey.stay_on_top]))
        self._apply_stay_on_top()

    # MARK: - Stay on top

    def _pin_button_changed(self, _):
        self._settings[SettingsKey.stay_on_top] = self._pin_button.get_active()
        self._settings.save()
        self._apply_stay_on_top()

        # A pinned window shows the run in its status bar, so the overlay is only needed while unpinned
        overlay = self._engine.overlay
        if overlay is not None:
            if self._pin_button.get_active():
                overlay.hide()
            else:
                overlay.show()

    # Stays above every other window, including after a run minimizes and restores it, until the pin is clicked again
    def _apply_stay_on_top(self):
        pinned = self._pin_button.get_active()
        self.is_stay_on_top = pinned

        self.set_keep_above(pinned)
        self._pin_button.set_tooltip_text("Stop keeping MouseMe on top" if pinned else "Keep MouseMe on top of other windows")

    # MARK: - Icon bar

    # A flat toggle button drawing off_icon while off and on_icon (in the accent color) while on; a filled icon is one closed shape
    def _icon_toggle(self, off_icon, on_icon, filled=False):
        button = Gtk.ToggleButton(relief=Gtk.ReliefStyle.NONE)
        area = Gtk.DrawingArea()
        area.set_size_request(_ICON_SIZE, _ICON_SIZE)
        area.connect("draw", self._draw_icon, button, off_icon, on_icon, filled)
        button.add(area)
        button.connect("toggled", lambda _: area.queue_draw())
        return button

    def _draw_icon(self, area, cr, button, off_icon, on_icon, filled):
        on = button.get_active()
        style = button.get_style_context()

        # While calibration is armed, the modes that can be calibrated are green
        if self._armed_mode_states is not None and button in self._calibratable_mode_buttons:
            color = Gdk.RGBA(0.18, 0.62, 0.26, 1)
        elif on:
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

        if filled:
            cr.close_path()
            cr.fill()
        else:
            cr.stroke()
        return False

    def _mode_changed(self, button):
        if self._reverting_mode_button:
            return

        # While calibration is armed, a mode icon picks the mode to calibrate rather than turning it on or off
        if self._calibrate_button.get_active():
            self._reverting_mode_button = True
            button.set_active(not button.get_active())
            self._reverting_mode_button = False
            self._calibrate_mode(button)
            return

        if button.get_active():
            for other in self._mode_buttons:
                if other is not button:
                    other.set_active(False)

            self._start_button.grab_focus()

        self._update_field_visibility()

    def _update_field_visibility(self):
        self.is_gbg_checked = self._gbg_check_box.get_active()
        self._swap_army_fields()

        # Army mode uses the editable fields too; QI, GBG and Build Menu show GBG's fixed values instead
        show_normal = not any(button.get_active() for button in (self._qi_check_box, self._gbg_check_box, self._build_menu_check_box))

        for field in (self._points_text, self._start_delay_text, self._loop_delay_text, self._delay_text, self._repetitions_text):
            field.set_visible(show_normal)

        for field in (self._points_gbg_text, self._start_delay_gbg_text, self._loop_delay_gbg_text, self._delay_gbg_text, self._repetitions_gbg_text):
            field.set_visible(not show_normal)

        self._refresh_status()

    # Shows Army's values and labels in the editable fields while Army mode is on, and normal mode's otherwise
    def _swap_army_fields(self):
        is_army = self._army_check_box.get_active()
        if is_army == self._showing_army_fields:
            return

        fields = (self._points_text, self._start_delay_text, self._loop_delay_text, self._delay_text, self._repetitions_text)
        shown_values = [field.get_text() for field in fields]
        for field, value in zip(fields, self._hidden_field_values):
            field.set_text(value)

        self._hidden_field_values = shown_values
        self._showing_army_fields = is_army
        self._points_label.set_text("Number of Units" if is_army else "Number of Points")
        self._start_delay_label.set_text("Army Delay (ms)" if is_army else "Start Delay (ms)")
        self._loop_delay_label.set_text("Close Delay (ms)" if is_army else "Loop Delay (ms)")

    # MARK: - Calibration

    # The modes that can be calibrated so far
    @property
    def _calibratable_mode_buttons(self):
        return [self._gbg_check_box, self._build_menu_check_box, self._army_check_box]

    def _calibrate_button_changed(self, _):
        if self._calibrate_button.get_active():
            # Show every mode as off, with the ones that can be calibrated in green, so the mode that's actually on
            # doesn't look like the one being calibrated. Disarming puts them back as they were.
            self._armed_mode_states = [button.get_active() for button in self._mode_buttons]
            self._set_mode_states([False] * len(self._mode_buttons))
            self._show_status("Pick mode", transient=False)
        else:
            states, self._armed_mode_states = self._armed_mode_states, None
            if states is not None:
                self._set_mode_states(states)
            self._show_status("")

        for button in self._mode_buttons:
            button.queue_draw()

    # Sets the mode icons without running any mode-change logic
    def _set_mode_states(self, states):
        self._reverting_mode_button = True
        for button, active in zip(self._mode_buttons, states):
            button.set_active(active)
        self._reverting_mode_button = False

    def _calibrate_mode(self, button):
        self._calibrate_button.set_active(False)

        if button not in self._calibratable_mode_buttons:
            # QI's spots are fixed
            self._show_status("QI can't be calibrated")
            return

        mode = RunMode.ARMY if button is self._army_check_box else RunMode.GBG if button is self._gbg_check_box else RunMode.BUILD_MENU
        self._engine.post(self._engine.calibrate, mode)

    # MARK: - Status

    # Called from the engine thread
    def show_status(self, text):
        GLib.idle_add(self._show_status, text)

    # Shows a message in the status line; a transient one clears itself after a few seconds unless replaced first.
    # An empty message clears straight away.
    def _show_status(self, text, transient=True):
        if not text:
            self._showing_message = False
            self._refresh_status()
            return False

        self._showing_message = True
        self._status_label.set_markup(f"<small>{GLib.markup_escape_text(text)}</small>")
        self._status_label.get_style_context().add_class("dim-label")
        self._status_version += 1

        if transient:
            version = self._status_version

            def clear():
                if self._status_version == version:
                    self._showing_message = False
                    self._refresh_status()
                return False

            GLib.timeout_add(3000, clear)

        return False

    # Mirrors the overlay, on the GTK thread; an empty text means the run has ended
    def _show_run_status(self, text, color):
        self._run_status_text = text
        self._run_status_color = color
        self._refresh_status()

    # The selected mode, shown in the status bar when nothing is running and no message is showing
    @property
    def _mode_name(self):
        if self._qi_check_box.get_active():
            return "QI mode"
        if self._gbg_check_box.get_active():
            return "GBG mode"
        if self._build_menu_check_box.get_active():
            return "Build mode"
        if self._army_check_box.get_active():
            return "Army mode"
        return "Normal mode"

    # Shows the run's text while a run is going, otherwise the selected mode, unless a message is showing.
    # QI's yellow is unreadable on a light window, so it shows darker here.
    def _refresh_status(self):
        if self._showing_message:
            return

        self._status_version += 1
        style = self._status_label.get_style_context()

        if self._run_status_text:
            shown = "#b8860b" if self._run_status_color == "#ffcc00" else self._run_status_color
            text = GLib.markup_escape_text(self._run_status_text)
            self._status_label.set_markup(f'<small><span foreground="{shown}">{text}</span></small>')
            style.remove_class("dim-label")
        else:
            self._status_label.set_markup(f"<small>{GLib.markup_escape_text(self._mode_name)}</small>")
            style.add_class("dim-label")

    # MARK: - Start

    # Called from the engine thread: while a QI or Build run is going, the Start button is Stop
    def show_stop_button(self, shown):
        GLib.idle_add(self._show_stop_button, shown)

    def _show_stop_button(self, shown):
        self._stop_button_shown = shown
        self._start_button.set_label("Stop" if shown else "Start")
        return False

    def _start_clicked(self, _):
        # During a QI or Build run the button is Stop, which ends the run the same way X does
        if self._stop_button_shown:
            self._engine.post(self._engine.cancel_run)
            return

        is_gbg = self._gbg_check_box.get_active()
        is_qi = self._qi_check_box.get_active()
        is_build_menu = self._build_menu_check_box.get_active()
        is_army = self._army_check_box.get_active()
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

        elif is_army:
            values = fields([
                (self._points_text, 1, "Please enter a number of 1 or more for Number of Units."),
                (self._start_delay_text, 0, "Please enter a number of 0 or more for Army Delay."),
                (self._loop_delay_text, 0, "Please enter a number of 0 or more for Close Delay."),
                (self._delay_text, 0, "Please enter a number of 0 or more for Delay."),
                (self._repetitions_text, 1, "Please enter a number of 1 or more for Repetitions."),
            ])
            if values is None:
                return
            # In Army mode, points is the number of units, start_delay is Army Delay and loop_delay is Close Delay
            settings = RunSettings(*values)

        elif not is_qi and not is_build_menu:
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

        # Normal and Army modes each save their own values; GBG uses fixed values and QI and Build Menu use none
        if is_army:
            s[SettingsKey.army_units] = settings.points
            s[SettingsKey.army_delay] = settings.start_delay
            s[SettingsKey.army_close_delay] = settings.loop_delay
            s[SettingsKey.army_click_delay] = settings.delay
            s[SettingsKey.army_repetitions] = settings.repetitions
        elif not is_gbg and not is_qi and not is_build_menu:
            s[SettingsKey.points] = settings.points
            s[SettingsKey.start_delay] = settings.start_delay
            s[SettingsKey.loop_delay] = settings.loop_delay
            s[SettingsKey.delay] = settings.delay
            s[SettingsKey.repetitions] = settings.repetitions

        s[SettingsKey.gbg] = is_gbg
        s[SettingsKey.qi] = is_qi
        s[SettingsKey.build_menu] = is_build_menu
        s[SettingsKey.army] = is_army
        s.save()

        # GBG and Army need their spots before they can run; calibrating brings the window back, ready for Start
        if is_gbg and self.gbg_target is None:
            self._engine.post(self._engine.calibrate, RunMode.GBG)
            return

        if is_army and self.army_targets is None:
            self._engine.post(self._engine.calibrate, RunMode.ARMY)
            return

        mode = RunMode.GBG if is_gbg else RunMode.QI if is_qi else RunMode.BUILD_MENU if is_build_menu else RunMode.ARMY if is_army else RunMode.NORMAL
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
