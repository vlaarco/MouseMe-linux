import asyncio
import enum
import random
import threading
import time
from dataclasses import dataclass

from .mouse import Mouse
from .qi_config import Key, QIConfig


@dataclass
class RunSettings:
    points: int = 1
    start_delay: int = 1000
    loop_delay: int = 1000
    delay: int = 250
    repetitions: int = 1


class RunMode(enum.Enum):
    NORMAL = "normal"
    GBG = "gbg"
    QI = "qi"


class Color:
    red = "#ff3b30"
    yellow = "#ffcc00"
    green = "#28cd41"


class _Stopped(Exception):
    pass


# Given to a "Which building?" wait when a toolbar or build menu click has already left Sell mode
_LEFT_PROMPT = "left-prompt"


# Recording, replay and QI logic. Everything runs on one asyncio loop on its own thread, including the event tap
# callbacks, so no locking is needed; the loops yield between steps with asyncio.sleep.
# UI calls (controller and overlay) are thread-safe and hop onto the GTK thread themselves.
class Engine:
    MOUSE_MARGIN = 4
    MOUSE_MOVE_CLICK_RATIO = 0.7

    # Physical input is never kept blocked longer than this, even if a sequence hangs
    MAX_SUPPRESS_SECONDS = 5

    def __init__(self, debug=False):
        self.debug = debug
        self.controller = None
        self.event_tap = None
        self.mouse = None

        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, name="Engine", daemon=True)

        self.overlay = None

        self._settings = RunSettings()
        self._click_positions = []
        self._recording = False

        # Incremented on every start so replay and QI loops from earlier runs can tell they're stale
        self._current_run_id = 0

        self._qi_active = False

        # True while QI waits at "Which building?"; a toolbar or build menu click ends the wait with _LEFT_PROMPT
        self._awaiting_building_key = False
        self._pending_key = None
        self._buffered_qi_key = None
        self._last_qi_key = None
        self._last_qi_confirm_key = None

        self._suppress_mouse_input = False
        self._suppress_token = 0

        # Which QI run turned suppression on, so an older run never releases a newer run's blocking
        self._suppress_owner_run_id = 0

    def start_thread(self):
        ready = threading.Event()
        self.loop.call_soon(ready.set)
        self._thread.start()
        ready.wait()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.mouse = Mouse()
        self.mouse.recover_detached()
        self.loop.run_forever()

    # Runs fn on the engine thread; safe to call from any thread
    def post(self, fn, *args):
        self.loop.call_soon_threadsafe(fn, *args)

    # Runs fn on the engine thread and waits for it to finish
    def call(self, fn, *args):
        done = threading.Event()

        def run():
            try:
                fn(*args)
            finally:
                done.set()

        self.post(run)
        done.wait(2)

    # MARK: - Starting and stopping

    def start(self, mode, settings):
        self._click_positions.clear()
        self._settings = settings

        self._current_run_id += 1
        self._set_qi_active(False)
        self._recording = False
        self._close_overlay()

        overlay = self.controller.create_overlay()
        self.overlay = overlay
        overlay.show()

        self.controller.minimize()

        if mode == RunMode.GBG:
            self._click_positions.append(QIConfig.gbg_click)

            overlay.set(str(settings.points), Color.red)

            positions = list(self._click_positions)
            self.loop.create_task(self._replay_clicks(self._current_run_id, positions, settings))

        elif mode == RunMode.QI:
            overlay.set("QI", Color.yellow)

            self._buffered_qi_key = None
            self._set_qi_active(True)
            self.loop.create_task(self._run_qi(self._current_run_id))

        else:
            overlay.set(str(settings.points), Color.green)

            self._recording = True

    async def _run_qi(self, run_id):
        try:
            await self._keyboard_clicks(run_id)
        finally:
            # Never leave physical mouse input blocked or keys captured once the QI loop ends
            self._release_mouse_input(run_id)

            if run_id == self._current_run_id:
                self._set_qi_active(False)

    # Moving or restoring the main window cancels whatever is running
    def cancel_run(self):
        if self.overlay is None:
            return

        self._recording = False
        self._close_overlay()

    def release_input(self):
        self._release_mouse_input()
        self._set_qi_active(False)
        self._cancel_pending_key()

    def _set_qi_active(self, active):
        if active != self._qi_active:
            self._qi_active = active
            self.event_tap.grab_qi_keys(active)

    def _stop_task(self, restore_window=True):
        self._close_overlay()

        if restore_window:
            self.controller.restore()

    def _close_overlay(self):
        if self.overlay is None:
            return

        self.overlay.close()
        self.overlay = None

        # End a QI loop waiting for a key so it can't be woken by a later run's overlay
        self._cancel_pending_key()

    def _cancel_pending_key(self):
        pending, self._pending_key = self._pending_key, None
        if pending is not None and not pending.done():
            pending.set_exception(_Stopped())

    # MARK: - Event tap

    def handle_key_down(self, key):
        if self.overlay is None or not self._qi_active:
            return

        # A key pressed mid-sequence is held (latest wins, except a held X is never replaced) until the QI loop next waits
        if self._pending_key is not None:
            pending, self._pending_key = self._pending_key, None
            if not pending.done():
                pending.set_result(key)
        elif self._buffered_qi_key != Key.x:
            self._buffered_qi_key = key

    def handle_left_click(self, x, y, from_xtest):
        injected = from_xtest and self.mouse.claim_injected_press()

        if self.debug:
            print(f"Mouse clicked at: {x}, {y}{' (injected)' if injected else ''}", flush=True)

        # A physical click in the browser tab strip means the tab may have changed, so the next QI key reruns its setup
        if y < QIConfig.tab_strip_max_y and not injected:
            self._last_qi_key = None

        # Clicking a toolbar button yourself during QI changes the game's mode the same way its QI key does, so the label follows
        if not injected and self._qi_active and self.overlay is not None:
            for key, (left, top, width, height) in QIConfig.toolbar_buttons.items():
                if left <= x < left + width and top <= y < top + height:
                    self.overlay.set_text(QIConfig.actions[key].label)
                    self._leave_building_prompt()

                    if key in QIConfig.transient_keys:
                        self._revert_to_qi_label_later(self._current_run_id)
                    break

        # Clicking in the build menu yourself during QI ends the game's Sell or Move mode
        mode_labels = {QIConfig.actions[key].label for key in QIConfig.mode_keys}
        in_build_menu = any(left <= x < left + width and top <= y < top + height for left, top, width, height in QIConfig.build_menu_areas)
        in_sell_or_move = self.overlay is not None and (self.overlay.text in mode_labels or self._awaiting_building_key)
        if not injected and self._qi_active and in_sell_or_move and in_build_menu:
            self.overlay.set_text("QI")
            self._leave_building_prompt()

        # Only record physical clicks, never ones injected by a replay
        overlay = self.overlay
        if overlay is None or not self._recording or injected:
            return

        self._click_positions.append((x, y))
        overlay.set_text(str(self._settings.points - len(self._click_positions)))

        if len(self._click_positions) < self._settings.points:
            return

        self._recording = False

        if not self.controller.is_minimized:
            self._close_overlay()
        else:
            overlay.set("", Color.red)

            positions = list(self._click_positions)
            self.loop.create_task(self._replay_clicks(self._current_run_id, positions, self._settings))

    # MARK: - Replay

    async def _replay_clicks(self, run_id, positions, settings):
        # A newer start owns the overlay; exit without touching it
        def is_stale():
            return run_id != self._current_run_id

        await self._sleep(settings.start_delay)

        start_position = self.mouse.location

        for i in range(max(settings.repetitions, 0)):
            if is_stale():
                return

            if self.overlay is None:
                break

            self.overlay.set_text(str(settings.repetitions - i))

            await self._sleep(settings.loop_delay)

            for position in positions:
                if is_stale():
                    return

                if self._user_moved_mouse(start_position, positions):
                    self._stop_task()
                    return

                await self._sleep(settings.delay)

                if is_stale():
                    return

                if self._user_moved_mouse(start_position, positions):
                    self._stop_task()
                    return

                await self._human_click(position, settings.delay, self.controller.is_gbg_checked)

        if not is_stale():
            self._stop_task()

    def _user_moved_mouse(self, start, positions):
        cx, cy = self.mouse.location

        def is_near(point):
            return abs(cx - point[0]) <= self.MOUSE_MARGIN and abs(cy - point[1]) <= self.MOUSE_MARGIN

        return not is_near(start) and not any(is_near(p) for p in positions)

    async def _human_click(self, position, delay, press_r):
        move_time = int(delay * self.MOUSE_MOVE_CLICK_RATIO)
        click_time = delay - move_time

        margin = self.MOUSE_MARGIN
        randomized = (position[0] + random.randint(-margin, margin), position[1] + random.randint(-margin, margin))

        await self._human_move(self.mouse.location, randomized, move_time)

        if press_r:
            self.mouse.press_key(Key.r)

        self.mouse.left_down(*randomized)
        await self._sleep(click_time // 2)
        self.mouse.left_up(*randomized)
        await self._sleep(click_time // 2)

    async def _human_move(self, start, end, duration_ms=50):
        if duration_ms <= 0:
            self.mouse.move(*end)
            return

        cp1 = (start[0] + random.randrange(-50, 50), start[1] + random.randrange(-50, 50))
        cp2 = (end[0] + random.randrange(-50, 50), end[1] + random.randrange(-50, 50))

        began = time.monotonic()
        duration = float(duration_ms)

        while True:
            elapsed = (time.monotonic() - began) * 1000
            if elapsed > duration:
                break

            t = min(elapsed / duration, 1)
            ease = t * t * (3 - 2 * t)
            u = 1 - ease

            x = u * u * u * start[0] + 3 * u * u * ease * cp1[0] + 3 * u * ease * ease * cp2[0] + ease * ease * ease * end[0]
            y = u * u * u * start[1] + 3 * u * u * ease * cp1[1] + 3 * u * ease * ease * cp2[1] + ease * ease * ease * end[1]

            self.mouse.move(x, y)
            await asyncio.sleep(0.001)

        self.mouse.move(*end)

    # MARK: - QI

    async def _keyboard_clicks(self, run_id):
        if self.overlay is None:
            return

        # A newer start owns the overlay; exit without touching it
        def is_stale():
            return run_id != self._current_run_id

        self._last_qi_key = None
        self._last_qi_confirm_key = None

        while True:
            if is_stale():
                return

            if self.overlay is None:
                break

            try:
                key = await self._wait_for_key()
            except _Stopped:
                return

            if is_stale():
                return

            overlay = self.overlay
            if overlay is None:
                break

            # Space confirms selling a building, so it's ignored unless the game is in Sell mode.
            # A prompt-ending click that arrived just after the prompt ended is ignored too.
            sell_label = QIConfig.actions[Key.s].label
            if key == _LEFT_PROMPT or (key == Key.space and overlay.text != sell_label):
                continue

            is_new_key = key != self._last_qi_key
            self._last_qi_key = key

            current_position = self.mouse.location

            if key == Key.space:
                overlay.set_text("Which building?")

                self._awaiting_building_key = True
                try:
                    building_key = await self._wait_for_key()
                except _Stopped:
                    return
                finally:
                    self._awaiting_building_key = False

                if is_stale():
                    return

                if building_key == _LEFT_PROMPT:
                    # A toolbar or build menu click already left Sell mode and set the label
                    self._last_qi_key = None
                    continue

                # Keep any movement made while choosing the building
                current_position = self.mouse.location

                if building_key == Key.x:
                    # X stops QI here too; Esc or a toolbar click leaves the prompt without stopping it
                    self._stop_task(restore_window=False)
                    return
                elif building_key != Key.space and building_key not in QIConfig.building_confirm:
                    # Not a building to sell, so it's a new command: leave the prompt and run it as usual
                    overlay.set_text(sell_label)

                    if self._buffered_qi_key is None:
                        self._buffered_qi_key = building_key

                    self._last_qi_key = None
                    continue
                elif self.overlay is not None:
                    if building_key == Key.space and self._last_qi_confirm_key is not None:
                        # Repeat last building confirm
                        building_key = self._last_qi_confirm_key

                    confirm_points = QIConfig.building_confirm.get(building_key)
                    if confirm_points:
                        self._last_qi_confirm_key = building_key
                        overlay.set_text(QIConfig.actions[building_key].label)
                        await self._perform_click_sequence(run_id, confirm_points)

                    # The game stays in Sell mode after selling, ready for the next building
                    overlay.set_text(sell_label)
                    self._last_qi_key = None

            elif key == Key.x:
                self._stop_task(restore_window=False)
                return

            else:
                action = QIConfig.actions.get(key)
                if action is not None:
                    overlay.set_text(action.label)

                    if is_new_key and action.setup:
                        await self._perform_click_sequence(run_id, action.setup)

                    await self._perform_click_sequence(run_id, action.clicks)

                    if key in QIConfig.transient_keys:
                        self._revert_to_qi_label_later(run_id)

            # A newer run owns the cursor now; just let go of any blocking this run started
            if is_stale():
                self._release_mouse_input(run_id)
                return

            # Only return the cursor if a click sequence took it over
            if self._suppress_mouse_input:
                await self._return_cursor(current_position, run_id)

        self._stop_task()

    # Puts "QI" back after a one-off action's label, unless a newer label or a newer run has taken over by then
    def _revert_to_qi_label_later(self, run_id):
        overlay = self.overlay
        if overlay is None:
            return

        version = overlay.text_version

        def revert():
            if run_id == self._current_run_id and self.overlay is overlay and overlay.text_version == version:
                overlay.set_text("QI")

        self.loop.call_later(QIConfig.transient_label_seconds, revert)

    # Ends a "Which building?" prompt after a click that left Sell mode, without treating the click as a building
    def _leave_building_prompt(self):
        if not self._awaiting_building_key:
            return

        if self._pending_key is not None:
            pending, self._pending_key = self._pending_key, None
            if not pending.done():
                pending.set_result(_LEFT_PROMPT)
        else:
            self._buffered_qi_key = _LEFT_PROMPT

    async def _wait_for_key(self):
        if self._buffered_qi_key is not None:
            key, self._buffered_qi_key = self._buffered_qi_key, None
            return key

        self._pending_key = self.loop.create_future()
        return await self._pending_key

    # Physical mouse input stays suppressed from the first click until return_cursor finishes
    async def _perform_click_sequence(self, run_id, points, delay=100):
        self._suppress_physical_mouse()
        self._suppress_owner_run_id = run_id

        for point in points:
            # Stop between clicks once the run is cancelled (window moved or restored) or replaced by a newer one
            if run_id != self._current_run_id or self.overlay is None:
                return

            await self._human_move(self.mouse.location, point)

            # Rest on the target before pressing, so the game has seen the pointer over it for a few frames
            await self._sleep(random.randint(40, 70))

            self.mouse.left_down(*point)
            await self._sleep(50)
            self.mouse.left_up(*point)
            await self._sleep(delay)

    # Moves the cursor back to its start position plus any physical movement made during the click sequence
    async def _return_cursor(self, start, run_id):
        try:
            dx, dy = self.event_tap.take_motion() if self._suppress_mouse_input else (0, 0)

            min_x, min_y, width, height = self.mouse.desktop_bounds
            target = (
                min(max(start[0] + dx, min_x), width - 1),
                min(max(start[1] + dy, min_y), height - 1),
            )

            await self._human_move(self.mouse.location, target, 50)
        finally:
            self._release_mouse_input(run_id)

    def _suppress_physical_mouse(self):
        if self._suppress_mouse_input:
            return

        self._suppress_mouse_input = True
        self._suppress_token += 1
        self.event_tap.track_motion(self.mouse.suppress_input())

        token = self._suppress_token
        self.loop.call_later(self.MAX_SUPPRESS_SECONDS, lambda: token == self._suppress_token and self._release_mouse_input())

    # Lets physical mouse input through again; given a run, only if that run started the blocking and no newer run has taken it over
    def _release_mouse_input(self, run_id=None):
        if not self._suppress_mouse_input or (run_id is not None and run_id != self._suppress_owner_run_id):
            return

        self._suppress_mouse_input = False
        self._suppress_token += 1
        self.event_tap.take_motion()
        self.mouse.release_input()

    async def _sleep(self, milliseconds):
        await asyncio.sleep(max(milliseconds, 0) / 1000)
