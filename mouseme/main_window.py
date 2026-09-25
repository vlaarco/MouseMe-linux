from gi.repository import Gdk, GLib, Gtk

from .engine import RunMode, RunSettings
from .overlay import OverlayPanel
from .settings import SettingsKey

# Window position is saved this long after the window stops moving, not on every pixel of a drag
_SAVE_POSITION_DELAY_MS = 500


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

        self._qi_check_box = Gtk.CheckButton(label="QI")
        self._gbg_check_box = Gtk.CheckButton(label="GBG")
        self._start_button = Gtk.Button(label="Start")

        self._build_ui()
        self._load_settings()

        self.set_resizable(False)
        if icon_path:
            self.set_icon_from_file(icon_path)

        position = settings[SettingsKey.window_position]
        if isinstance(position, list) and len(position) == 2:
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

        rows = [
            ("Number of Points", self._points_text, self._points_gbg_text),
            ("Start Delay (ms)", self._start_delay_text, self._start_delay_gbg_text),
            ("Loop Delay (ms)", self._loop_delay_text, self._loop_delay_gbg_text),
            ("Delay (ms)", self._delay_text, self._delay_gbg_text),
            ("Repetitions", self._repetitions_text, self._repetitions_gbg_text),
        ]

        for i, (title, field, gbg_field) in enumerate(rows):
            label = Gtk.Label(label=title, xalign=0)
            grid.attach(label, 0, i, 1, 1)

            cell = Gtk.Box()
            cell.pack_start(field, True, True, 0)
            cell.pack_start(gbg_field, True, True, 0)
            grid.attach(cell, 1, i, 1, 1)

        check_boxes = Gtk.Box(spacing=8)
        check_boxes.pack_start(self._qi_check_box, False, False, 0)
        check_boxes.pack_start(self._gbg_check_box, False, False, 0)
        grid.attach(check_boxes, 0, len(rows), 1, 1)

        self._qi_check_box.connect("toggled", self._qi_check_box_changed)
        self._gbg_check_box.connect("toggled", self._gbg_check_box_changed)

        self._start_button.set_can_default(True)
        self._start_button.connect("clicked", self._start_clicked)
        grid.attach(self._start_button, 1, len(rows), 1, 1)

        self.add(grid)
        self.set_default(self._start_button)
        self._start_button.grab_focus()

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
