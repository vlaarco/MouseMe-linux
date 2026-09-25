import ctypes
import os
import queue
import select
import threading

from . import x11
from .qi_config import QIConfig

# QI keys are grabbed with and without these, so Caps Lock and Num Lock don't stop the grab from matching
_LOCK_COMBOS = [0, x11.LockMask, x11.Mod2Mask, x11.LockMask | x11.Mod2Mask]

# QI keys pressed with Ctrl, Alt or Super are never grabbed, so browser and desktop shortcuts keep working
_SHORTCUT_MASK = x11.ControlMask | x11.Mod1Mask | x11.Mod4Mask


# System-wide mouse and keyboard watcher; the X11 counterpart of the macOS event tap and Windows low-level hooks.
# Runs on its own thread with its own display connection and reports to the engine through callbacks.
#
# X can't veto individual events the way a tap or hook can, so swallowing works differently:
# - QI keys are grabbed while QI is active, so their key-down and key-up go only to MouseMe
# - physical pointers are detached from the cursor during click sequences (see Mouse.suppress_input)
class EventTap(threading.Thread):
    def __init__(self, on_key_down, on_left_click):
        super().__init__(name="EventTap", daemon=True)

        # on_key_down(key_name) and on_left_click(x, y, from_xtest) are called on this thread
        self._on_key_down = on_key_down
        self._on_left_click = on_left_click

        self._display = x11.open_display()
        self._root = x11.XDefaultRootWindow(self._display)
        self._xi_opcode = x11.xi_opcode(self._display)

        self._keycodes = {x11.keycode(self._display, name): name for name in QIConfig.keys}

        devices = x11.devices(self._display)
        self._master_pointer = next(d.id for d in devices if d.use == x11.XIMasterPointer)
        self._xtest_ids = {d.id for d in devices if d.is_xtest}

        self._commands = queue.Queue()
        self._wake_r, self._wake_w = os.pipe()

        # Movement of detached physical pointers, summed for returnCursor
        self._motion_lock = threading.Lock()
        self._motion_ids = frozenset()
        self._dx = 0.0
        self._dy = 0.0

        self._select_raw_events()

    def _select_raw_events(self):
        mask = (ctypes.c_ubyte * 4)()
        for evtype in (x11.XI_RawButtonPress, x11.XI_RawMotion):
            mask[evtype >> 3] |= 1 << (evtype & 7)

        # All devices, not just masters, so detached pointers still report movement
        event_mask = x11.XIEventMask(x11.XIAllDevices, len(mask), mask)
        x11.XISelectEvents(self._display, self._root, ctypes.byref(event_mask), 1)
        x11.XFlush(self._display)

    # MARK: - Called from other threads

    def grab_qi_keys(self, grab):
        self._commands.put(grab)
        os.write(self._wake_w, b"\0")

    def track_motion(self, device_ids):
        with self._motion_lock:
            self._motion_ids = frozenset(device_ids)
            self._dx = 0.0
            self._dy = 0.0

    def take_motion(self):
        with self._motion_lock:
            dx, dy = self._dx, self._dy
            self._motion_ids = frozenset()
            self._dx = 0.0
            self._dy = 0.0
            return dx, dy

    # MARK: - Event loop

    def run(self):
        fd = x11.XConnectionNumber(self._display)
        event = x11.XEvent()

        while True:
            self._run_commands()
            x11.XFlush(self._display)

            while x11.XPending(self._display):
                x11.XNextEvent(self._display, ctypes.byref(event))
                self._dispatch(event)

            readable, _, _ = select.select([fd, self._wake_r], [], [], 1.0)
            if self._wake_r in readable:
                os.read(self._wake_r, 1024)

    def _run_commands(self):
        while True:
            try:
                grab = self._commands.get_nowait()
            except queue.Empty:
                return

            for keycode in self._keycodes:
                for base in (0, x11.ShiftMask):
                    for lock in _LOCK_COMBOS:
                        if grab:
                            x11.XGrabKey(self._display, keycode, base | lock, self._root, False, x11.GrabModeAsync, x11.GrabModeAsync)
                        else:
                            x11.XUngrabKey(self._display, keycode, base | lock, self._root)

    def _dispatch(self, event):
        if event.type == x11.KeyPress:
            key = event.xkey
            name = self._keycodes.get(key.keycode)

            # While a grabbed key is held the whole keyboard is grabbed, so other keys can arrive here too
            if name is not None and not key.state & _SHORTCUT_MASK:
                self._on_key_down(name)
            return

        if event.type != x11.GenericEvent:
            return

        cookie = event.xcookie
        if cookie.extension != self._xi_opcode or not x11.XGetEventData(self._display, ctypes.byref(cookie)):
            return

        try:
            raw = ctypes.cast(cookie.data, ctypes.POINTER(x11.XIRawEvent)).contents

            if cookie.evtype == x11.XI_RawMotion:
                self._add_motion(raw)

            elif cookie.evtype == x11.XI_RawButtonPress and raw.deviceid == self._master_pointer and raw.detail == 1:
                x, y = x11.query_pointer(self._display)
                self._on_left_click(x, y, raw.sourceid in self._xtest_ids)
        finally:
            x11.XFreeEventData(self._display, ctypes.byref(cookie))

    def _add_motion(self, raw):
        with self._motion_lock:
            if raw.deviceid not in self._motion_ids:
                return

            state = raw.valuators
            index = 0
            dx = dy = 0.0

            for axis in range(state.mask_len * 8):
                if state.mask[axis >> 3] & (1 << (axis & 7)):
                    if axis == 0:
                        dx = state.values[index]
                    elif axis == 1:
                        dy = state.values[index]
                    index += 1

                if axis >= 1:
                    break

            self._dx += dx
            self._dy += dy
