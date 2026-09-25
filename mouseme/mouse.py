import collections
import json
import os
import time

from . import x11

# An injected press not seen by the event tap within this many seconds is forgotten
_INJECTED_PRESS_TIMEOUT = 1.0

# Physical pointers MouseMe has detached, kept on disk so a crash can't leave the mouse dead after the next launch
_STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "MouseMe")
_STATE_FILE = os.path.join(_STATE_DIR, "detached-pointers.json")


# Synthesizes mouse and keyboard input through XTest. Injected events come from the XTEST devices,
# which is how the event tap tells them from physical input. Only use from the engine thread.
class Mouse:
    def __init__(self):
        self._display = x11.open_display()
        self._screen = x11.XDefaultScreen(self._display)
        self._detached = []

        # When each click MouseMe sent was pressed, oldest first, until the event tap sees it
        self._injected_presses = collections.deque()

    @property
    def location(self):
        return x11.query_pointer(self._display)

    # The whole X screen, which spans every monitor
    @property
    def desktop_bounds(self):
        return 0, 0, x11.XDisplayWidth(self._display, self._screen), x11.XDisplayHeight(self._display, self._screen)

    def move(self, x, y):
        x11.XTestFakeMotionEvent(self._display, -1, int(round(x)), int(round(y)), 0)
        x11.XFlush(self._display)

    def left_down(self, x, y):
        self._button(x, y, True)

    def left_up(self, x, y):
        self._button(x, y, False)

    def press_key(self, keysym_name):
        keycode = x11.keycode(self._display, keysym_name)
        for down in (True, False):
            x11.XTestFakeKeyEvent(self._display, keycode, down, 0)
        x11.XFlush(self._display)

    # Tools like Synergy also inject through XTest, so an XTest click only counts as MouseMe's own if one was just sent
    def claim_injected_press(self):
        now = time.monotonic()
        while self._injected_presses and now - self._injected_presses[0] > _INJECTED_PRESS_TIMEOUT:
            self._injected_presses.popleft()

        if not self._injected_presses:
            return False

        self._injected_presses.popleft()
        return True

    def _button(self, x, y, down):
        if down:
            self._injected_presses.append(time.monotonic())

        x11.XTestFakeMotionEvent(self._display, -1, int(round(x)), int(round(y)), 0)
        x11.XTestFakeButtonEvent(self._display, 1, down, 0)
        x11.XFlush(self._display)

    # MARK: - Blocking physical input

    # Detaches every physical pointer from the cursor, so moves, clicks and scrolls go nowhere while XTest keeps working.
    # Returns the ids of the detached pointers that move relatively, whose movement can still be tracked.
    def suppress_input(self):
        if self._detached:
            return [d.id for d in self._detached if not d.absolute]

        self._detached = [d for d in x11.devices(self._display) if d.use == x11.XISlavePointer and not d.is_xtest]
        _save_state(self._detached)

        x11.change_hierarchy(self._display, [x11.detach(d.id) for d in self._detached])
        return [d.id for d in self._detached if not d.absolute]

    def release_input(self):
        if not self._detached:
            return

        detached, self._detached = self._detached, []
        x11.change_hierarchy(self._display, [x11.attach(d.id, d.attachment) for d in detached])
        _clear_state()

    # Reattaches pointers a previous run left detached, if it crashed or was killed mid-sequence
    def recover_detached(self):
        try:
            with open(_STATE_FILE) as f:
                saved = json.load(f)
        except (OSError, ValueError):
            return

        floating = {d.id: d for d in x11.devices(self._display) if d.use == x11.XIFloatingSlave}
        changes = [
            x11.attach(entry["id"], entry["master"])
            for entry in saved
            if entry["id"] in floating and floating[entry["id"]].name == entry["name"]
        ]

        x11.change_hierarchy(self._display, changes)
        _clear_state()


def _save_state(devices):
    os.makedirs(_STATE_DIR, exist_ok=True)
    with open(_STATE_FILE, "w") as f:
        json.dump([{"id": d.id, "name": d.name, "master": d.attachment} for d in devices], f)


def _clear_state():
    try:
        os.remove(_STATE_FILE)
    except FileNotFoundError:
        pass
