from dataclasses import dataclass, field
from typing import Dict, List, Tuple

Point = Tuple[float, float]


# X keysym names for the keys MouseMe listens for; mapped to keycodes at startup
class Key:
    space = "space"
    escape = "Escape"
    b = "b"
    c = "c"
    d = "d"
    e = "e"
    f = "f"
    m = "m"
    p = "p"
    r = "r"
    s = "s"
    t = "t"
    v = "v"
    x = "x"
    y = "y"
    z = "z"
    one = "1"
    two = "2"
    three = "3"
    four = "4"
    q = "q"


# The game's spots that Build and QI click. Both modes calibrate them and share them, so calibrating either updates both.
class Spot:
    build = "Build"
    top_left = "TopLeft"
    top_right = "TopRight"
    bottom_left = "BottomLeft"
    bottom_right = "BottomRight"
    residential_tab = "ResidentialTab"
    fourth_tab = "FourthTab"  # Culture in QI's build menu and Expansions in a settlement's, in the same place
    first_page = "FirstPage"
    previous_page = "PreviousPage"
    next_page = "NextPage"
    last_page = "LastPage"
    sell = "Sell"
    move = "Move"
    flat_mode = "FlatMode"
    cancel = "Cancel"

    prompts = {
        build: "Click Build",
        top_left: "Click Top Left",
        top_right: "Click Top Right",
        bottom_left: "Click Bottom Left",
        bottom_right: "Click Bottom Right",
        residential_tab: "Click Residential Tab",
        fourth_tab: "Click Culture Tab",
        first_page: "Click First Page",
        previous_page: "Click Previous Page",
        next_page: "Click Next Page",
        last_page: "Click Last Page",
        sell: "Click Sell",
        move: "Click Move",
        flat_mode: "Click Flat Mode",
        cancel: "Click Cancel",
    }


# One click in a QI or Build action: a calibrated spot, or a build menu category tab counted from the top (1 is the
# Residential tab). The tabs are evenly spaced, so the 1st and 4th tabs give the spot of every tab.
@dataclass(frozen=True)
class QIStep:
    spot: str = Spot.residential_tab
    tab: int = 0

    def point(self, spots):
        if self.tab == 0:
            return spots[self.spot]

        (x1, y1), (x4, y4) = spots[Spot.residential_tab], spots[Spot.fourth_tab]
        step = (self.tab - 1) / 3
        return (round(x1 + (x4 - x1) * step), round(y1 + (y4 - y1) * step))


def _at(spot):
    return QIStep(spot=spot)


def _tab(number):
    return QIStep(tab=number)


@dataclass(frozen=True)
class QIAction:
    label: str

    # Clicked only when this key differs from the previous QI key
    setup: List[QIStep] = field(default_factory=list)

    # Clicked on every press
    clicks: List[QIStep] = field(default_factory=list)


# All coordinates are root-window pixels with the origin at the top-left of the screen
class QIConfig:
    label = "QI"

    # In calibration order: the build menu, then the toolbar
    calibration_spots = [
        Spot.build, Spot.top_left, Spot.top_right, Spot.bottom_left, Spot.bottom_right,
        Spot.residential_tab, Spot.fourth_tab, Spot.first_page, Spot.previous_page, Spot.next_page, Spot.last_page,
        Spot.sell, Spot.move, Spot.flat_mode, Spot.cancel,
    ]

    keys = [
        Key.space,
        Key.escape,
        Key.b,
        Key.c,
        Key.d,
        Key.e,
        Key.f,
        Key.m,
        Key.p,
        Key.s,
        Key.t,
        Key.v,
        Key.x,
        Key.y,
        Key.z,
    ]

    # Space and X are handled separately: Space picks a building to confirm, X stops QI.
    # A building is found by its category tab, its page (First Page, then Next Page for page 2) and its slot.
    actions: Dict[str, QIAction] = {
        Key.b: QIAction("Brewery", setup=[_tab(2), _at(Spot.first_page), _at(Spot.next_page)], clicks=[_at(Spot.bottom_right)]),
        Key.c: QIAction("Church", setup=[_tab(4), _at(Spot.first_page)], clicks=[_at(Spot.bottom_right)]),
        Key.d: QIAction("Doctor", setup=[_tab(4), _at(Spot.first_page), _at(Spot.next_page)], clicks=[_at(Spot.top_left)]),
        Key.e: QIAction("Estate", setup=[_tab(1), _at(Spot.first_page), _at(Spot.next_page)], clicks=[_at(Spot.bottom_left)]),
        Key.escape: QIAction("Cancel", clicks=[_at(Spot.cancel)]),
        Key.f: QIAction("Flat Mode", clicks=[_at(Spot.flat_mode)]),
        Key.m: QIAction("Multistory", setup=[_tab(1), _at(Spot.first_page)], clicks=[_at(Spot.top_left)]),
        Key.p: QIAction("Pillory", setup=[_tab(4), _at(Spot.first_page)], clicks=[_at(Spot.bottom_left)]),
        Key.s: QIAction("Sell", clicks=[_at(Spot.sell)]),
        Key.t: QIAction("Tannery", setup=[_tab(2), _at(Spot.first_page)], clicks=[_at(Spot.bottom_left)]),
        Key.v: QIAction("Move", clicks=[_at(Spot.move)]),
        Key.y: QIAction("Bakery", setup=[_tab(2), _at(Spot.first_page)], clicks=[_at(Spot.top_left)]),
        Key.z: QIAction("Build", clicks=[_at(Spot.build)]),
    }

    # The buildings Space can sell. Each sell dialog's checkbox and confirm button sit in a different place, so each
    # building learns its own the first time it's sold; recalibrating QI clears them, since the dialogs move with the game.
    building_keys = {Key.b, Key.c, Key.d, Key.e, Key.m, Key.t, Key.y}
    confirm_prompts = ["Click Checkbox", "Click Confirm"]

    # Actions whose label reverts to "QI" after a few seconds; every other label stays until the next key
    transient_keys = {Key.escape, Key.f, Key.z}
    transient_label_seconds = 3

    # The toolbar buttons by QI key. Clicking one yourself changes the game's mode just like its QI key does, so the
    # label follows either way.
    toolbar_spots = {Key.s: Spot.sell, Key.v: Spot.move, Key.f: Spot.flat_mode, Key.escape: Spot.cancel}
    toolbar_button_size = 43

    # A toolbar button's area around its spot, as (left, top, width, height)
    @staticmethod
    def toolbar_button(spot):
        size = QIConfig.toolbar_button_size
        return (spot[0] - size / 2, spot[1] - size / 2, size, size)

    # The build menu the Build button opens (with the panel below it) and the category tabs down its right side,
    # as (left, top, width, height). Clicking in either yourself ends the game's Sell or Move mode, so those labels go
    # back to "QI". The menu runs from the left edge to the tabs, and from its title bar above the slots to the bottom
    # of the screen; the tabs run from the Residential tab down past the 7th.
    @staticmethod
    def build_menu_areas(spots):
        if not all(spot in spots for spot in (Spot.top_left, Spot.residential_tab, Spot.fourth_tab)):
            return []

        top_left, first, fourth = spots[Spot.top_left], spots[Spot.residential_tab], spots[Spot.fourth_tab]
        tab_spacing = (fourth[1] - first[1]) / 3
        tabs_left = first[0] - 15
        return [
            (0, top_left[1] - 120, tabs_left, 100_000),
            (tabs_left, first[1] - tab_spacing / 2, 35, tab_spacing * 7),
        ]

    mode_keys = {Key.s, Key.v}

    # A physical click above this line is in the browser tab strip
    tab_strip_max_y = 106


# Build Menu mode: each key clicks its own calibrated spot; the calibrate button sets them
class BuildMenuConfig:
    label = "Build"

    # Each key's spot: the Build button, the four build menu slots (1 to 4: top left, top right, bottom left, bottom right),
    # and the Sell, Move, Flat Mode and Cancel toolbar buttons
    key_spots = {
        Key.z: Spot.build, Key.one: Spot.top_left, Key.two: Spot.top_right, Key.three: Spot.bottom_left,
        Key.four: Spot.bottom_right, Key.s: Spot.sell, Key.v: Spot.move, Key.f: Spot.flat_mode, Key.escape: Spot.cancel,
    }

    # Shift with 1 to 4 clicks the settlement build menu's four category tabs instead, counted from the top
    tab_keys = [Key.one, Key.two, Key.three, Key.four]

    # In calibration order; the Residential and Expansions (4th) tabs give the spot of every tab
    calibration_spots = [
        Spot.build, Spot.top_left, Spot.top_right, Spot.bottom_left, Spot.bottom_right, Spot.residential_tab, Spot.fourth_tab,
        Spot.sell, Spot.move, Spot.flat_mode, Spot.cancel,
    ]
    calibration_prompts = ["Click Expansions Tab" if spot == Spot.fourth_tab else Spot.prompts[spot] for spot in calibration_spots]

    keys = list(dict.fromkeys(list(key_spots) + tab_keys + [Key.x]))


# GBG mode clicks one calibrated spot: the sweet spot where all of a battle's buttons overlap. Calibration records your
# clicks (which still reach the game) as you fight, and saves the spot once enough clicks in a row land in the same place.
class GbgConfig:
    calibration_prompt = "Click GBG spot"

    # How many clicks in a row must land within spot_tolerance pixels of the first of them
    clicks_needed = 4
    spot_tolerance = 2


# Army mode: deletes units from the army, clicking five calibrated spots
class ArmyConfig:
    label = "Army"

    # Waited once after Start is pressed, before the first Army click; not shown in the window
    start_delay_ms = 2000

    # How long a run takes, in milliseconds. Each click takes about Delay (moving there, then pressing), so a repetition
    # is its Army, Delete Unit and Close clicks, each unit's Unit and Delete Confirm clicks, and the waits after each.
    @staticmethod
    def run_time_ms(units, army_delay, close_delay, delay, repetitions):
        repetition = army_delay + close_delay + 4 * delay + 4 * units * delay
        return ArmyConfig.start_delay_ms + repetitions * repetition

    # A run time as "2h05m", "33m" or "40s"
    @staticmethod
    def format_run_time(ms):
        seconds = round(ms / 1000)
        if seconds < 60:
            return f"{seconds}s"

        minutes = round(ms / 60_000)
        return f"{minutes}m" if minutes < 60 else f"{minutes // 60}h{minutes % 60:02d}m"

    # The spots, in calibration order
    ARMY, DELETE_UNIT, UNIT, DELETE_CONFIRM, CLOSE = range(5)
    calibration_prompts = ["Click Army", "Click Delete Unit", "Click Unit", "Click Delete Confirm", "Click Close"]
